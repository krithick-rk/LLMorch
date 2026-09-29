"""
LLMorch SoC Verification Repositories (Persistence Layer)
Provides typed SQLite CRUD access for verification plans, work packages, specifications,
requirements, SoC components, coverage items, gaps, policies, and closure snapshots.
"""

from __future__ import annotations

import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from history.database import DatabaseService
from schemas.soc_verification import (
    VerificationPlan,
    WorkPackage,
    Specification,
    Requirement,
    SoCComponent,
    CoverageItem,
    Gap,
    PolicyCandidate,
    ClosureSnapshot,
    PlanStatus,
    WorkPackageStatus,
    CostTier,
    ExecutionRecommendationMode,
)
from schemas.soc_ontology import SoCBucket


class VerificationPlanRepository:
    def __init__(self, db: DatabaseService):
        self.db = db

    def save(self, plan: VerificationPlan) -> None:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO verification_plans (
                    plan_id, project_id, version, repository_path, repository_name, scope_description,
                    status, buckets_applicability, total_requirements, total_objectives,
                    total_work_packages, total_estimated_tokens, total_estimated_duration_seconds,
                    cost_tier, recommendation_mode, replan_reason, parent_plan_id,
                    created_by, created_at, approved_by, approved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan.plan_id, plan.project_id, plan.version, plan.repository_path, plan.repository_name, plan.scope_description,
                plan.status.value, json.dumps(plan.buckets_applicability), plan.total_requirements, plan.total_objectives,
                plan.total_work_packages, plan.total_estimated_tokens, plan.total_estimated_duration_seconds,
                plan.cost_tier.value, plan.recommendation_mode.value, plan.replan_reason, plan.parent_plan_id,
                plan.created_by, plan.created_at, plan.approved_by, plan.approved_at
            ))
            conn.commit()

    def get(self, plan_id: str) -> Optional[VerificationPlan]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM verification_plans WHERE plan_id = ?", (plan_id,)).fetchone()
            if not row:
                return None
            return self._row_to_plan(row)

    def get_latest_for_repository(self, repository_path: str, project_id: Optional[str] = None) -> Optional[VerificationPlan]:
        with self.db.get_connection() as conn:
            if project_id:
                row = conn.execute("""
                    SELECT * FROM verification_plans
                    WHERE repository_path = ? AND project_id = ?
                    ORDER BY version DESC, created_at DESC
                    LIMIT 1
                """, (repository_path, project_id)).fetchone()
            else:
                row = conn.execute("""
                    SELECT * FROM verification_plans
                    WHERE repository_path = ?
                    ORDER BY version DESC, created_at DESC
                    LIMIT 1
                """, (repository_path,)).fetchone()
            if not row:
                return None
            return self._row_to_plan(row)

    def list_all(self, limit: int = 50, project_id: Optional[str] = None) -> List[VerificationPlan]:
        with self.db.get_connection() as conn:
            if project_id:
                rows = conn.execute(
                    "SELECT * FROM verification_plans WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                    (project_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM verification_plans ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [self._row_to_plan(r) for r in rows]

    def update_status(self, plan_id: str, status: PlanStatus, approved_by: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc).isoformat() if approved_by else None
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE verification_plans
                SET status = ?, approved_by = COALESCE(?, approved_by), approved_at = COALESCE(?, approved_at)
                WHERE plan_id = ?
            """, (status.value, approved_by, now, plan_id))
            conn.commit()

    def _row_to_plan(self, row) -> VerificationPlan:
        d = dict(row)
        return VerificationPlan(
            project_id=d.get("project_id"),
            plan_id=d["plan_id"],
            version=d["version"],
            repository_path=d["repository_path"],
            repository_name=d["repository_name"],
            scope_description=d["scope_description"],
            status=PlanStatus(d["status"]),
            buckets_applicability=json.loads(d["buckets_applicability"] or "{}"),
            total_requirements=d["total_requirements"],
            total_objectives=d["total_objectives"],
            total_work_packages=d["total_work_packages"],
            total_estimated_tokens=d["total_estimated_tokens"],
            total_estimated_duration_seconds=d["total_estimated_duration_seconds"],
            cost_tier=CostTier(d["cost_tier"]),
            recommendation_mode=ExecutionRecommendationMode(d["recommendation_mode"]),
            replan_reason=d["replan_reason"],
            parent_plan_id=d["parent_plan_id"],
            created_by=d["created_by"],
            created_at=d["created_at"],
            approved_by=d["approved_by"],
            approved_at=d["approved_at"]
        )


class WorkPackageRepository:
    def __init__(self, db: DatabaseService):
        self.db = db

    def save(self, wp: WorkPackage) -> None:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO work_packages (
                    package_id, plan_id, name, description, bucket, role, objective_ids,
                    target_files, dependencies, estimated_tokens, estimated_duration_seconds,
                    cost_tier, recommendation_mode, status, assigned_agent_id, created_at, project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                wp.package_id, wp.plan_id, wp.name, wp.description, wp.bucket.value, wp.role,
                json.dumps(wp.objective_ids), json.dumps(wp.target_files), json.dumps(wp.dependencies),
                wp.estimated_tokens, wp.estimated_duration_seconds, wp.cost_tier.value,
                wp.recommendation_mode.value, wp.status.value, wp.assigned_agent_id, wp.created_at, wp.project_id
            ))
            conn.commit()

    def get(self, package_id: str) -> Optional[WorkPackage]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM work_packages WHERE package_id = ?", (package_id,)).fetchone()
            if not row:
                return None
            return self._row_to_wp(row)

    def list_for_plan(self, plan_id: str) -> List[WorkPackage]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM work_packages WHERE plan_id = ? ORDER BY created_at ASC", (plan_id,)).fetchall()
            return [self._row_to_wp(r) for r in rows]

    def update_status(self, package_id: str, status: WorkPackageStatus) -> None:
        with self.db.get_connection() as conn:
            conn.execute("UPDATE work_packages SET status = ? WHERE package_id = ?", (status.value, package_id))
            conn.commit()

    def _row_to_wp(self, row) -> WorkPackage:
        d = dict(row)
        return WorkPackage(
            project_id=d.get("project_id"),
            package_id=d["package_id"],
            plan_id=d["plan_id"],
            name=d["name"],
            description=d["description"],
            bucket=SoCBucket(d["bucket"]),
            role=d["role"],
            objective_ids=json.loads(d["objective_ids"] or "[]"),
            target_files=json.loads(d["target_files"] or "[]"),
            dependencies=json.loads(d["dependencies"] or "[]"),
            estimated_tokens=d["estimated_tokens"],
            estimated_duration_seconds=d["estimated_duration_seconds"],
            cost_tier=CostTier(d["cost_tier"]),
            recommendation_mode=ExecutionRecommendationMode(d["recommendation_mode"]),
            status=WorkPackageStatus(d["status"]),
            assigned_agent_id=d["assigned_agent_id"],
            created_at=d["created_at"]
        )


class SpecificationRepository:
    def __init__(self, db: DatabaseService):
        self.db = db

    def save(self, spec: Specification) -> None:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO specifications (
                    spec_id, title, document_type, file_path, revision, sections_count,
                    requirements_extracted, extracted_claims, assumptions, content_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                spec.spec_id, spec.title, spec.document_type, spec.file_path, spec.revision,
                spec.sections_count, spec.requirements_extracted, json.dumps(spec.extracted_claims),
                json.dumps(spec.assumptions), spec.content_hash, spec.created_at
            ))
            conn.commit()

    def get(self, spec_id: str) -> Optional[Specification]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM specifications WHERE spec_id = ?", (spec_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            return Specification(
                spec_id=d["spec_id"],
                title=d["title"],
                document_type=d["document_type"],
                file_path=d["file_path"],
                revision=d["revision"],
                sections_count=d["sections_count"],
                requirements_extracted=d["requirements_extracted"],
                extracted_claims=json.loads(d["extracted_claims"] or "[]"),
                assumptions=json.loads(d["assumptions"] or "[]"),
                content_hash=d["content_hash"],
                created_at=d["created_at"]
            )

    def list_all(self) -> List[Specification]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM specifications ORDER BY created_at DESC").fetchall()
            res = []
            for row in rows:
                d = dict(row)
                res.append(Specification(
                    spec_id=d["spec_id"],
                    title=d["title"],
                    document_type=d["document_type"],
                    file_path=d["file_path"],
                    revision=d["revision"],
                    sections_count=d["sections_count"],
                    requirements_extracted=d["requirements_extracted"],
                    extracted_claims=json.loads(d["extracted_claims"] or "[]"),
                    assumptions=json.loads(d["assumptions"] or "[]"),
                    content_hash=d["content_hash"],
                    created_at=d["created_at"]
                ))
            return res


class RequirementRepository:
    def __init__(self, db: DatabaseService):
        self.db = db

    def save(self, req: Requirement) -> None:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO requirements (
                    requirement_id, spec_id, section, title, description, primary_bucket,
                    affected_components, is_security_critical, claims, assumptions, provenance,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                req.requirement_id, req.spec_id, req.section, req.title, req.description,
                req.primary_bucket.value, json.dumps(req.affected_components), 1 if req.is_security_critical else 0,
                json.dumps(req.claims), json.dumps(req.assumptions), req.provenance, req.status, req.created_at
            ))
            conn.commit()

    def list_for_spec(self, spec_id: str) -> List[Requirement]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM requirements WHERE spec_id = ?", (spec_id,)).fetchall()
            return [self._row_to_req(r) for r in rows]

    def list_all(self, limit: int = 200) -> List[Requirement]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM requirements ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [self._row_to_req(r) for r in rows]

    def _row_to_req(self, row) -> Requirement:
        d = dict(row)
        return Requirement(
            requirement_id=d["requirement_id"],
            spec_id=d["spec_id"],
            section=d["section"],
            title=d["title"],
            description=d["description"],
            primary_bucket=SoCBucket(d["primary_bucket"]),
            affected_components=json.loads(d["affected_components"] or "[]"),
            is_security_critical=bool(d["is_security_critical"]),
            claims=json.loads(d["claims"] or "[]"),
            assumptions=json.loads(d["assumptions"] or "[]"),
            provenance=d["provenance"] or "extracted",
            status=d["status"],
            created_at=d["created_at"]
        )


class ClosureRepository:
    def __init__(self, db: DatabaseService):
        self.db = db

    def save_snapshot(self, snap: ClosureSnapshot) -> None:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO closure_snapshots (
                    snapshot_id, plan_id, run_id, requirement_coverage_pct, objective_coverage_pct,
                    total_requirements, covered_requirements, total_objectives, covered_objectives,
                    open_gaps_count, waivers_count, evidence_items_count, is_closed, sign_off_by,
                    sign_off_notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snap.snapshot_id, snap.plan_id, snap.run_id, snap.requirement_coverage_pct,
                snap.objective_coverage_pct, snap.total_requirements, snap.covered_requirements,
                snap.total_objectives, snap.covered_objectives, snap.open_gaps_count,
                snap.waivers_count, snap.evidence_items_count, 1 if snap.is_closed else 0,
                snap.sign_off_by, snap.sign_off_notes, snap.created_at
            ))
            conn.commit()

    def get_latest_for_plan(self, plan_id: str) -> Optional[ClosureSnapshot]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM closure_snapshots WHERE plan_id = ? ORDER BY created_at DESC LIMIT 1", (plan_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            return ClosureSnapshot(
                snapshot_id=d["snapshot_id"],
                plan_id=d["plan_id"],
                run_id=d["run_id"],
                requirement_coverage_pct=d["requirement_coverage_pct"],
                objective_coverage_pct=d["objective_coverage_pct"],
                total_requirements=d["total_requirements"],
                covered_requirements=d["covered_requirements"],
                total_objectives=d["total_objectives"],
                covered_objectives=d["covered_objectives"],
                open_gaps_count=d["open_gaps_count"],
                waivers_count=d["waivers_count"],
                evidence_items_count=d["evidence_items_count"],
                is_closed=bool(d["is_closed"]),
                sign_off_by=d["sign_off_by"],
                sign_off_notes=d["sign_off_notes"],
                created_at=d["created_at"]
            )


class PolicyCandidateRepository:
    def __init__(self, db: DatabaseService):
        self.db = db

    def save(self, policy: PolicyCandidate) -> None:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO policy_candidates (
                    policy_id, title, rule_expression, bucket, justification, status,
                    provenance, generated_from_requirement_id, created_at, reviewed_by,
                    review_notes, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                policy.policy_id, policy.title, policy.rule_expression,
                policy.bucket.value if hasattr(policy.bucket, "value") else str(policy.bucket),
                policy.justification, policy.status, policy.provenance, policy.generated_from_requirement_id,
                policy.created_at, policy.reviewed_by, policy.review_notes, policy.reviewed_at
            ))
            conn.commit()

    def get(self, policy_id: str) -> Optional[PolicyCandidate]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM policy_candidates WHERE policy_id = ?", (policy_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            return PolicyCandidate(**d)

    def list_all(self, status: Optional[str] = None) -> List[PolicyCandidate]:
        with self.db.get_connection() as conn:
            if status:
                rows = conn.execute("SELECT * FROM policy_candidates WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM policy_candidates ORDER BY created_at DESC").fetchall()
            return [PolicyCandidate(**dict(r)) for r in rows]
