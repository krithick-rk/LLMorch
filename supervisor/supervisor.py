"""
LLMorch Supervisor Layer
Implements planning, interpretation, intent normalization, 23-bucket ontology mapping,
WorkPackage decomposition, and execution cost estimation.
The Supervisor outputs versioned proposals/plans and does NOT act as runtime authority.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from schemas.soc_ontology import SoCBucket, BucketApplicability, SOC_BUCKET_DEFINITIONS
from schemas.soc_verification import (
    VerificationPlan,
    WorkPackage,
    VerificationObjective,
    VerificationScenario,
    CostTier,
    ExecutionRecommendationMode,
    PlanStatus,
    WorkPackageStatus,
    Requirement,
    Specification,
)
from repository_intelligence.preflight import PreflightReport, RepositoryClassification
from repository_intelligence.complexity import (
    ComplexityTier, IntentDepth, classify_complexity,
    parse_intent_depth, evaluate_bucket_evidence, get_task_limit_for_tier
)


class Supervisor:
    """
    Supervisor Planner Layer.
    Translates analyst intent and technical specs into a structured, versioned VerificationPlan.
    """

    def __init__(self, repo_path: Optional[str] = None, *args, **kwargs):
        self.repo_path = repo_path

    def synthesize_verification_plan(
        self,
        repository_path: str,
        repository_name: str,
        intent_objective: Optional[str] = None,
        preflight: Optional[PreflightReport] = None,
        specifications: Optional[List[Specification]] = None,
        requirements: Optional[List[Requirement]] = None,
        analysis_units: Optional[List[Any]] = None,
        parent_plan: Optional[VerificationPlan] = None
    ) -> Tuple[VerificationPlan, List[WorkPackage], List[VerificationObjective], List[Dict[str, Any]]]:
        """
        Synthesizes a versioned VerificationPlan proposal.
        Supervisor produces plans; Orchestrator executes approved plans.
        """
        version = (parent_plan.version + 1) if parent_plan else 1
        plan_id = f"vplan-{uuid.uuid4().hex[:8]}"

        # 1. Evaluate Preflight Feasibility
        if preflight and preflight.is_terminal:
            # Deterministic immediate completion for empty or non-analyzable repositories
            plan = VerificationPlan(
                plan_id=plan_id,
                version=version,
                repository_path=repository_path,
                repository_name=repository_name,
                scope_description=f"Preflight audit completed: {preflight.summary_text}",
                status=PlanStatus.COMPLETED,
                buckets_applicability={b.value: BucketApplicability.NOT_APPLICABLE.value for b in SoCBucket},
                applicability_reasons={b.value: "Preflight audit completed with terminal status" for b in SoCBucket},
                complexity_tier=ComplexityTier.MICRO.value,
                intent_depth=IntentDepth.QUICK.value,
                total_requirements=0,
                total_objectives=0,
                total_work_packages=0,
                total_estimated_tokens=0,
                total_estimated_duration_seconds=0,
                cost_tier=CostTier.LIGHTWEIGHT,
                recommendation_mode=ExecutionRecommendationMode.AUTO_EXECUTE,
                parent_plan_id=parent_plan.plan_id if parent_plan else None
            )
            return plan, [], [], []

        # 2. Deterministic Complexity Tier & Domain Evidence (Section 15, 16, 17)
        tier, evidence = classify_complexity(
            repo_path=repository_path,
            analyzable_files_count=preflight.analyzable_files_count if preflight else 2,
            total_bytes=preflight.total_bytes if preflight else 5000,
            rtl_detected=preflight.rtl_detected if preflight else True,
            software_detected=preflight.software_detected if preflight else False,
            build_system_detected=preflight.build_system_detected if preflight else False
        )
        depth = parse_intent_depth(intent_objective, tier)

        # 3. Determine Evidence-Driven 23-Bucket Applicability (Section 18 & 26)
        bucket_applicability: Dict[str, str] = {}
        applicability_reasons: Dict[str, str] = {}
        for bucket in SoCBucket:
            app, reason = evaluate_bucket_evidence(
                bucket=bucket,
                tier=tier,
                intent=depth,
                evidence=evidence,
                rtl_detected=preflight.rtl_detected if preflight else True,
                software_detected=preflight.software_detected if preflight else False
            )
            bucket_applicability[bucket.value] = app.value
            applicability_reasons[bucket.value] = reason

        # 4. Formulate Verification Objectives from applicable buckets and requirements
        objectives: List[VerificationObjective] = []
        req_list = requirements or []

        # Sort applicable buckets by architectural relevance
        applicable_buckets = [b for b in SoCBucket if bucket_applicability.get(b.value) == BucketApplicability.APPLICABLE.value]
        max_tasks = get_task_limit_for_tier(tier, depth)

        # Bound applicable buckets to max_tasks for small repositories (Section 19)
        if len(applicable_buckets) > max_tasks:
            priority_order = [
                SoCBucket.RESETS, SoCBucket.CLOCKS, SoCBucket.IP_BOUNDARY,
                SoCBucket.SECURITY, SoCBucket.CONNECTIVITY, SoCBucket.CDC,
                SoCBucket.CLOSURE
            ]
            prioritized = [b for b in priority_order if b in applicable_buckets]
            other_b = [b for b in applicable_buckets if b not in prioritized]
            applicable_buckets = (prioritized + other_b)[:max_tasks]

        for soc_b in applicable_buckets:
            b_def = SOC_BUCKET_DEFINITIONS[soc_b]
            matched_reqs = [r for r in req_list if r.primary_bucket == soc_b]
            if matched_reqs:
                for r in matched_reqs:
                    obj = VerificationObjective(
                        requirement_id=r.requirement_id,
                        bucket=soc_b,
                        title=f"{b_def.name}: {r.title}",
                        statement=f"Verify {b_def.name} conformance to requirement '{r.title}': {r.description[:100]}",
                        target_components=r.affected_components or [repository_name],
                        verification_method="SIMULATION" if soc_b in (SoCBucket.CONNECTIVITY, SoCBucket.CROSS_IP_FLOWS) else "FORMAL"
                    )
                    objectives.append(obj)
            else:
                obj = VerificationObjective(
                    bucket=soc_b,
                    title=f"{b_def.name} Verification",
                    statement=f"Verify structural and functional {b_def.name} integrity ({b_def.scope_description})",
                    target_components=[repository_name],
                    verification_method="STATIC_LINT" if soc_b in (SoCBucket.IP_BOUNDARY, SoCBucket.CLOCKS, SoCBucket.RESETS) else "SIMULATION"
                )
                objectives.append(obj)

        # 5. Decompose Objectives into Bounded Work Packages
        work_packages: List[WorkPackage] = []
        proposed_questions: List[Dict[str, Any]] = []

        objs_by_bucket: Dict[SoCBucket, List[VerificationObjective]] = {}
        for obj in objectives:
            objs_by_bucket.setdefault(obj.bucket, []).append(obj)

        for bucket, b_objs in objs_by_bucket.items():
            b_def = SOC_BUCKET_DEFINITIONS[bucket]
            wp_id = f"wp-{uuid.uuid4().hex[:8]}"

            # Scaled token and duration estimation (Section 20 & 21)
            if tier == ComplexityTier.MICRO:
                est_tokens = len(b_objs) * 4000 + 2000
                est_seconds = len(b_objs) * 30 + 15
            elif tier == ComplexityTier.SMALL:
                est_tokens = len(b_objs) * 6000 + 4000
                est_seconds = len(b_objs) * 45 + 30
            else:
                est_tokens = len(b_objs) * 12000 + 8000
                est_seconds = len(b_objs) * 60 + 60

            cost_tier = CostTier.LIGHTWEIGHT if est_tokens < 30000 else (CostTier.MODERATE if est_tokens < 100000 else CostTier.EXPENSIVE)

            wp = WorkPackage(
                package_id=wp_id,
                plan_id=plan_id,
                name=f"WP: {b_def.name} Verification",
                description=f"Bounded work package targeting {len(b_objs)} objectives under {b_def.name}",
                bucket=bucket,
                role=b_def.recommended_role,
                objective_ids=[o.objective_id for o in b_objs],
                estimated_tokens=est_tokens,
                estimated_duration_seconds=est_seconds,
                cost_tier=cost_tier,
                recommendation_mode=ExecutionRecommendationMode.AUTO_EXECUTE if cost_tier == CostTier.LIGHTWEIGHT else ExecutionRecommendationMode.RECOMMEND_EXECUTION,
                status=WorkPackageStatus.PROPOSED
            )
            work_packages.append(wp)

        # Check for Missing Context or Ambiguities requiring Analyst Decision
        if preflight and not preflight.build_system_detected and preflight.rtl_detected and tier not in (ComplexityTier.MICRO, ComplexityTier.SMALL):
            proposed_questions.append({
                "question_id": f"q-build-{uuid.uuid4().hex[:6]}",
                "reason": "Missing build/compilation metadata for RTL simulation",
                "question": "No Makefile or BUILD file detected for RTL sources. How should simulation harnesses be compiled?",
                "options": [
                    "Auto-generate Verilator lint and compilation script",
                    "Use Yosys generic synthesis pre-check",
                    "Awaiting analyst-provided build script",
                    "Proceed with static analysis only"
                ],
                "default_option": "Auto-generate Verilator lint and compilation script"
            })

        # Separate token breakdown (Section 20)
        repo_bytes = preflight.total_bytes if preflight else 4000
        repo_tokens = max(500, repo_bytes // 4)
        plan_tokens = 3000 if tier == ComplexityTier.MICRO else (6000 if tier == ComplexityTier.SMALL else 15000)
        exec_tokens = sum(wp.estimated_tokens for wp in work_packages)
        total_tokens = repo_tokens + plan_tokens + exec_tokens
        total_duration = sum(wp.estimated_duration_seconds for wp in work_packages)

        total_cost_tier = CostTier.LIGHTWEIGHT if total_tokens < 50000 else (
            CostTier.MODERATE if total_tokens < 200000 else CostTier.EXPENSIVE
        )
        plan_rec_mode = ExecutionRecommendationMode.AUTO_EXECUTE if total_cost_tier == CostTier.LIGHTWEIGHT else (
            ExecutionRecommendationMode.RECOMMEND_EXECUTION if total_cost_tier == CostTier.MODERATE else ExecutionRecommendationMode.REQUIRE_REVIEW
        )

        plan = VerificationPlan(
            plan_id=plan_id,
            version=version,
            repository_path=repository_path,
            repository_name=repository_name,
            scope_description=intent_objective or f"Adaptive {tier.value} Verification Plan for {repository_name}",
            status=PlanStatus.DRAFT,
            buckets_applicability=bucket_applicability,
            applicability_reasons=applicability_reasons,
            complexity_tier=tier.value,
            intent_depth=depth.value,
            repository_tokens=repo_tokens,
            planning_tokens=plan_tokens,
            execution_tokens=exec_tokens,
            total_requirements=len(req_list),
            total_objectives=len(objectives),
            total_work_packages=len(work_packages),
            total_estimated_tokens=total_tokens,
            total_estimated_duration_seconds=total_duration,
            cost_tier=total_cost_tier,
            recommendation_mode=plan_rec_mode,
            estimated_tokens=total_tokens,
            recommendation=plan_rec_mode.value,
            parent_plan_id=parent_plan.plan_id if parent_plan else None
        )

        return plan, work_packages, objectives, proposed_questions

    def propose_replan(
        self,
        current_plan: VerificationPlan,
        failed_work_package: WorkPackage,
        failure_reason: str,
        analyst_instruction: Optional[str] = None
    ) -> Tuple[VerificationPlan, List[WorkPackage]]:
        """
        Generates a new plan revision (v2, v3...) responding to a failed task or tool failure.
        Preserves plan history without mutating prior versions.
        """
        new_plan_id = f"vplan-{uuid.uuid4().hex[:8]}"
        new_version = current_plan.version + 1

        replan_reason = f"Replanning WP '{failed_work_package.name}' following failure: {failure_reason}"
        if analyst_instruction:
            replan_reason += f" | Analyst instruction: {analyst_instruction}"

        new_plan = current_plan.model_copy(update={
            "plan_id": new_plan_id,
            "version": new_version,
            "status": PlanStatus.DRAFT,
            "parent_plan_id": current_plan.plan_id,
            "replan_reason": replan_reason,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        # Create updated work packages with modified tool or split method
        updated_wps = []
        new_wp = failed_work_package.model_copy(update={
            "package_id": f"wp-{uuid.uuid4().hex[:8]}",
            "plan_id": new_plan_id,
            "name": f"{failed_work_package.name} (Revised)",
            "description": f"Revised strategy for {failed_work_package.name}. Reason: {failure_reason}",
            "status": WorkPackageStatus.PROPOSED
        })
        updated_wps.append(new_wp)

        return new_plan, updated_wps

    def create_verification_plan(
        self,
        intent: str,
        repository_path: str,
        repository_name: Optional[str] = None,
        author: Optional[str] = "Analyst"
    ) -> VerificationPlan:
        """Convenience method to synthesize and persist a VerificationPlan."""
        from repository_intelligence.preflight import analyze_repository_preflight
        from history.database import DatabaseService
        from history.soc_repositories import VerificationPlanRepository, WorkPackageRepository

        p = Path(repository_path).resolve()
        preflight = analyze_repository_preflight(str(p))
        plan, wps, objs, questions = self.synthesize_verification_plan(
            repository_path=str(p),
            repository_name=repository_name or p.name,
            intent_objective=intent,
            preflight=preflight,
        )
        plan.author = author or "Analyst"
        plan.objectives = objs
        plan.work_packages = wps

        try:
            db = DatabaseService()
            plan_repo = VerificationPlanRepository(db)
            wp_repo = WorkPackageRepository(db)
            plan_repo.save(plan)
            for wp in wps:
                wp_repo.save(wp)
        except Exception:
            pass
        return plan

    def propose_replan(
        self,
        plan_id: str,
        reason: str,
        trigger: str = "MANUAL_REPLAN",
        failed_package_id: Optional[str] = None,
        analyst_instruction: Optional[str] = None
    ) -> VerificationPlan:
        """Convenience method to propose a plan revision v1 -> v2."""
        from history.database import DatabaseService
        from history.soc_repositories import VerificationPlanRepository, WorkPackageRepository

        db = DatabaseService()
        plan_repo = VerificationPlanRepository(db)
        parent_plan = plan_repo.get(plan_id)

        new_plan = VerificationPlan(
            plan_id=f"vplan-{uuid.uuid4().hex[:8]}",
            version=(parent_plan.version + 1) if parent_plan else 2,
            parent_plan_id=plan_id,
            repository_path=parent_plan.repository_path if parent_plan else "",
            repository_name=parent_plan.repository_name if parent_plan else "",
            scope_description=parent_plan.scope_description if parent_plan else f"Replanned verification for {plan_id}",
            status=PlanStatus.DRAFT,
            cost_tier=parent_plan.cost_tier if parent_plan else CostTier.MODERATE,
            recommendation_mode=parent_plan.recommendation_mode if parent_plan else ExecutionRecommendationMode.RECOMMEND_EXECUTION,
            total_estimated_tokens=parent_plan.total_estimated_tokens if parent_plan else 50000,
            total_estimated_duration_seconds=parent_plan.total_estimated_duration_seconds if parent_plan else 300,
            total_work_packages=parent_plan.total_work_packages if parent_plan else 1,
            author="Supervisor",
            replan_reason=reason,
        )
        plan_repo.save(new_plan)
        return new_plan

    def _determine_bucket_applicability(
        self,
        bucket: SoCBucket,
        preflight: Optional[PreflightReport],
        analysis_units: Optional[List[Any]] = None
    ) -> BucketApplicability:
        """
        Deterministically evaluates whether a bucket is APPLICABLE, NOT_APPLICABLE, or UNKNOWN.
        """
        if not preflight:
            return BucketApplicability.UNKNOWN

        if preflight.is_terminal:
            return BucketApplicability.NOT_APPLICABLE

        tier, evidence = classify_complexity(
            repo_path=preflight.repository_path,
            analyzable_files_count=preflight.analyzable_files_count,
            total_bytes=preflight.total_bytes,
            rtl_detected=preflight.rtl_detected,
            software_detected=preflight.software_detected,
            build_system_detected=preflight.build_system_detected
        )
        app, _ = evaluate_bucket_evidence(
            bucket=bucket,
            tier=tier,
            intent=IntentDepth.STANDARD,
            evidence=evidence,
            rtl_detected=preflight.rtl_detected,
            software_detected=preflight.software_detected
        )
        return app


# Module-level alias
SoCSupervisor = Supervisor
