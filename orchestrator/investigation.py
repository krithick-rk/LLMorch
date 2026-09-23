"""
LLMorch Adaptive Multi-Agent Vulnerability Investigation Workflow Engine (Phase 6)
Orchestrates adaptive multi-agent execution with durable FailoverEngine recovery
and persistent Cross-Project Research Memory (Project Memory, Global Patterns, Promotion Gate, and Verification).
"""

import os
import json
import hashlib
import concurrent.futures
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import uuid

from schemas.task import Task, TaskStatus, RiskLevel
from schemas.agent import Agent, AgentInterface
from schemas.health import AgentHealthState
from schemas.event import Event, EventType
from schemas.evidence import Evidence, EvidenceSourceType
from schemas.finding import Finding, FindingState, FindingLocation
from schemas.agent_selection import AgentSelectionRequest
from schemas.task_result import TaskResult
from schemas.strategy import StrategyDecision, AgentAssignment
from schemas.errors import ErrorCode, LLMorchError, QuotaExhaustedError, AgentUnavailableError
from schemas.memory import (
    PatternDomain,
    MemoryConfidence,
    MemoryPrivacyClass,
    ProjectMemoryRecord,
    ResearchOutcomeRecord,
    ApplicabilityStatus,
)

from orchestrator.state_machine import TaskStateMachine, FindingStateMachine
from registry.agent_registry import AgentRegistry
from adapters.base import BaseAgentAdapter
from adapters.agy_adapter import AGYAdapter
from adapters.claude_adapter import ClaudeAdapter
from adapters.codex_adapter import CodexAdapter
from orchestrator.strategy import StrategyEngine
from scheduler.failover import FailoverEngine
from repository_intelligence.intake import RepositoryIntake, RepositorySnapshot
from repository_intelligence.noise_filter import NoiseFilter
from tools.precheck import DeterministicPreChecker
from sandbox.workspace import WorkspaceManager, Workspace
from validator.engine import FindingValidator, ValidationResult
from correlation.engine import FindingCorrelator, CorrelationResult
from memory.service import MemoryService
from memory.promotion import PromotionEngine
from memory.applicability import LLMApplicabilityVerifier
from history.database import DatabaseService
from history.repositories import (
    TaskRepository,
    AgentRepository,
    RunRepository,
    EventRepository,
    CheckpointRepository,
)


class InvestigationWorkflow:
    """
    Phase 6 Memory-Informed, Failover-Aware Investigation Orchestrator.
    Dynamically sizes and executes agent discovery tasks guided by Global Research Memory,
    with durable checkpoint recovery and privacy-controlled pattern promotion.
    """

    def __init__(
        self,
        repo_path: str,
        target_component: str,
        preferred_agent_id: Optional[str] = None,
        preferred_agent_ids: Optional[List[str]] = None,
        requested_agent_count: Optional[int] = None,
        domain: PatternDomain = PatternDomain.GENERIC,
        budget: float = 100.0,
        db_service: Optional[DatabaseService] = None,
        strategy_config: Optional[Dict[str, Any]] = None,
        testing_config: Optional[Dict[str, Any]] = None
    ):
        self.repo_path = repo_path
        self.target_component = target_component
        self.preferred_agent_id = preferred_agent_id
        self.preferred_agent_ids = preferred_agent_ids
        self.requested_agent_count = requested_agent_count
        self.domain = domain
        self.budget = budget
        self.testing_config = testing_config or {}
        self.workflow_id = f"wf-{uuid.uuid4().hex[:12]}"
        self.project_id = f"proj-{hashlib.sha256(repo_path.encode()).hexdigest()[:12]}"
        self.db = db_service or DatabaseService()

        self.task_repo = TaskRepository(self.db)
        self.agent_repo = AgentRepository(self.db)
        self.run_repo = RunRepository(self.db)
        self.event_repo = EventRepository(self.db)
        self.chk_repo = CheckpointRepository(self.db)

        self.registry = AgentRegistry()
        self.workspace_mgr = WorkspaceManager()

        # Phase 6 Memory Components
        self.memory_service = MemoryService(self.db)
        self.promotion_engine = PromotionEngine(self.db)
        self.applicability_verifier = LLMApplicabilityVerifier(self.db)

        # Initialize Adapters
        self.adapters: Dict[str, BaseAgentAdapter] = {
            "agent-agy-01": AGYAdapter(),
            "agent-claude-01": ClaudeAdapter(),
            "agent-codex-01": CodexAdapter(),
            "agent-fourth-01": CodexAdapter(),
        }

        # Register Available Agents in Registry
        for agent_id, adapter in self.adapters.items():
            provider = "antigravity" if "agy" in agent_id else ("anthropic" if "claude" in agent_id else ("openai" if "codex" in agent_id else "auxiliary"))
            agent = Agent(
                agent_id=agent_id,
                provider=provider,
                interface=AgentInterface.CLI,
                model="runtime-resolved",
                capabilities=adapter.capabilities(),
                health=adapter.health(),
                availability=True,
                adapter_version=adapter.version()
            )
            self.registry.register_agent(agent)
            self.agent_repo.save(agent)

        self.strategy_engine = StrategyEngine(self.registry, config=strategy_config or {"max_agents": 4})
        self.failover_engine = FailoverEngine(self.db, self.registry, self.workspace_mgr)

    def _execute_child_task(
        self,
        root_task: Task,
        child_index: int,
        assignment: AgentAssignment,
        snapshot: RepositorySnapshot,
        scoped_paths: List[str],
        precheck_res: Any,
        memory_patterns_context: str
    ) -> Dict[str, Any]:
        """
        Executes one child discovery task independently inside an isolated workspace.
        Receives retrieved global research patterns for memory-informed hypothesis generation.
        """
        agent = self.registry.get_agent(assignment.agent_id)
        adapter = self.adapters.get(assignment.agent_id, self.adapters["agent-agy-01"])

        child_task = Task(
            parent_task_id=root_task.task_id,
            workflow_id=self.workflow_id,
            objective=f"Memory-informed research pass #{child_index + 1} ({assignment.role}): Investigate security weaknesses in {self.target_component}",
            assigned_agent_id=agent.agent_id,
            required_capabilities=assignment.required_capabilities,
            risk_level=RiskLevel.MEDIUM
        )
        self.task_repo.save(child_task)

        self.event_repo.record(Event(
            event_type=EventType.AGENT_ROLE_ASSIGNED,
            actor="orchestrator",
            payload={"child_task_id": child_task.task_id, "agent_id": agent.agent_id, "role": assignment.role}
        ))

        # Separate Workspace per Agent
        workspace = self.workspace_mgr.create_workspace(
            repo_root=snapshot.absolute_root,
            workflow_id=self.workflow_id,
            task_id=child_task.task_id,
            git_commit=snapshot.git_commit
        )
        child_task.workspace_policy.allowed_paths = [workspace.working_directory]

        # Context Isolation with Memory Patterns
        context_prompt = (
            f"Child Task ID: {child_task.task_id}\n"
            f"Assigned Role: {assignment.role}\n"
            f"Task Objective: {child_task.objective}\n"
            f"Repository Root: {snapshot.absolute_root}\n"
            f"Target Scope: {scoped_paths[:10]}\n"
            f"Precheck Findings: {precheck_res.findings[:3]}\n"
            f"--- GLOBAL RESEARCH MEMORY PATTERNS ---\n{memory_patterns_context}\n"
            "INDEPENDENT DISCOVERY PHASE: Analyze target component independently. Provide security hypothesis and affected locations."
        )

        child_task, _ = TaskStateMachine.transition(child_task, TaskStatus.DISPATCHED, actor="orchestrator")
        child_task, run_evt = TaskStateMachine.transition(child_task, TaskStatus.RUNNING, actor=agent.agent_id)
        self.task_repo.save(child_task)
        self.event_repo.record(run_evt)

        # Test Failure Injection Verification
        sim_quota = self.testing_config.get("simulate_quota_exhaustion_for", [])
        sim_crash = self.testing_config.get("simulate_crash_for", [])

        if agent.agent_id in sim_quota:
            res = self.failover_engine.handle_failure_and_recover(
                task_id=child_task.task_id,
                failed_run_id=f"run-sim-quota-{child_task.task_id}",
                error_code=ErrorCode.QUOTA_EXHAUSTED,
                failure_reason=f"Simulated quota exhaustion for {agent.agent_id}",
                execution_context={"repo_path": snapshot.absolute_root}
            )
            if res.get("status") == "RESUMED":
                replacement_id = res["replacement_agent_id"]
                agent = self.registry.get_agent(replacement_id)
                adapter = self.adapters.get(replacement_id, self.adapters["agent-agy-01"])

        elif agent.agent_id in sim_crash:
            res = self.failover_engine.handle_failure_and_recover(
                task_id=child_task.task_id,
                failed_run_id=f"run-sim-crash-{child_task.task_id}",
                error_code=ErrorCode.AGENT_PROCESS_FAILURE,
                failure_reason=f"Simulated crash failure for {agent.agent_id}",
                execution_context={"repo_path": snapshot.absolute_root}
            )
            if res.get("status") == "RESUMED":
                replacement_id = res["replacement_agent_id"]
                agent = self.registry.get_agent(replacement_id)
                adapter = self.adapters.get(replacement_id, self.adapters["agent-agy-01"])

        exec_res = adapter.execute_task_sync(child_task, workspace.working_directory, context_prompt)
        run = exec_res["run"]
        self.run_repo.save(run)

        task_result = adapter.normalize_result(exec_res["stdout"])

        raw_hash = hashlib.sha256(exec_res["stdout"].encode()).hexdigest()
        evidence = Evidence(
            task_id=child_task.task_id,
            run_id=run.run_id,
            agent_id=agent.agent_id,
            source_type=EvidenceSourceType.TOOL_OUTPUT if exec_res["exit_code"] == 0 else EvidenceSourceType.AGENT_CLAIM,
            raw_hash=raw_hash,
            canonical_hash=raw_hash,
            semantic_fingerprint=f"sem-{raw_hash[:12]}",
            environment_fingerprint=run.environment_fingerprint,
            exit_status=run.exit_status
        )

        self.event_repo.record(Event(
            run_id=run.run_id,
            event_type=EventType.EVIDENCE_RECORDED,
            actor=agent.agent_id,
            payload={"evidence_id": evidence.evidence_id, "child_task_id": child_task.task_id}
        ))

        child_task, complete_evt = TaskStateMachine.transition(
            child_task,
            TaskStatus.SUCCEEDED if run.status.value == "SUCCEEDED" else TaskStatus.FAILED,
            actor="orchestrator"
        )
        self.task_repo.save(child_task)
        self.event_repo.record(complete_evt)

        return {
            "child_task": child_task,
            "agent_id": agent.agent_id,
            "provider": agent.provider,
            "role": assignment.role,
            "run_id": run.run_id,
            "exec_res": exec_res,
            "task_result": task_result,
            "evidence": evidence,
            "workspace": workspace.working_directory
        }

    def run(self) -> Dict[str, Any]:
        """
        Executes end-to-end Phase 6 Memory-Informed Workflow.
        """
        # 1. Repository Intake & Snapshot
        intake = RepositoryIntake(self.repo_path)
        snapshot = intake.create_snapshot()

        # 2. Scope & Prechecks
        target_dir = Path(snapshot.absolute_root) / self.target_component
        raw_paths = []
        if target_dir.exists():
            for root, dirs, files in os.walk(target_dir):
                for f in files:
                    raw_paths.append(os.path.join(root, f))
        else:
            raw_paths.append(str(Path(snapshot.absolute_root) / "pyproject.toml"))

        scoped_paths = NoiseFilter.filter_paths_for_llm(raw_paths, snapshot.absolute_root)
        precheck_res = DeterministicPreChecker.run_prechecks(scoped_paths)

        # 3. Phase 6 Memory Retrieval & Applicability Verification
        target_context_str = f"{self.target_component} {' '.join(scoped_paths[:5])} {' '.join(precheck_res.findings)}"
        retrieved_memories = self.memory_service.retrieve(
            project_id=self.project_id,
            domain=self.domain,
            target_context=target_context_str,
            scoped_indicators=precheck_res.findings
        )

        applicable_patterns = []
        memory_lines = []
        for mem in retrieved_memories:
            app_res = self.applicability_verifier.verify_applicability(mem.pattern, scoped_paths, precheck_res.findings)
            if app_res.status in [ApplicabilityStatus.APPLICABLE, ApplicabilityStatus.UNCERTAIN]:
                applicable_patterns.append(mem.pattern)
                memory_lines.append(f"- [Pattern {mem.pattern.pattern_id}] {mem.pattern.title}: {app_res.reasoning_summary}")

        memory_patterns_context = "\n".join(memory_lines) if memory_lines else "No matching global research patterns retrieved."

        # 4. Create Root Task
        root_task = Task(
            workflow_id=self.workflow_id,
            objective=f"Phase 6 Memory-Informed Investigation on target '{self.target_component}'",
            required_capabilities=["repository_analysis", "security_review"],
            risk_level=RiskLevel.MEDIUM
        )
        self.task_repo.save(root_task)
        self.event_repo.record(Event(event_type=EventType.TASK_CREATED, actor="orchestrator", payload={"task_id": root_task.task_id}))

        # 5. Strategy Engine Evaluation
        pref_ids = self.preferred_agent_ids or ([self.preferred_agent_id] if self.preferred_agent_id else None)
        forced_count = self.requested_agent_count
        if self.preferred_agent_ids:
            forced_count = len(self.preferred_agent_ids)
        elif self.preferred_agent_id:
            forced_count = 1

        decision, assignments = self.strategy_engine.evaluate(
            task=root_task,
            scoped_paths=scoped_paths,
            precheck_count=len(precheck_res.findings),
            forced_agent_count=forced_count,
            budget_available=self.budget,
            preferred_agent_ids=pref_ids
        )

        if not assignments or decision.chosen_agent_count == 0:
            return {
                "error": "INSUFFICIENT_AGENT_CAPACITY",
                "details": "No eligible agents available matching task constraints",
                "strategy_decision": decision.model_dump()
            }

        root_task, _ = TaskStateMachine.transition(root_task, TaskStatus.DISPATCHED, actor="orchestrator")
        root_task, fork_evt = TaskStateMachine.transition(root_task, TaskStatus.RUNNING, actor="orchestrator")
        self.task_repo.save(root_task)

        # 6. Execute Multi-Agent Discovery
        child_results: List[Dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(decision.chosen_agent_count, 1)) as executor:
            futures = [
                executor.submit(self._execute_child_task, root_task, idx, assignment, snapshot, scoped_paths, precheck_res, memory_patterns_context)
                for idx, assignment in enumerate(assignments)
            ]
            child_results = [f.result() for f in futures]

        # 7. Post-Discovery Correlation & Validation
        evidences = [r["evidence"] for r in child_results]
        correlation_res = FindingCorrelator.correlate_results(child_results, evidences)

        # Build Representative Finding & Run Validator
        best_hypothesis = child_results[0]["task_result"].hypothesis if child_results else "Security vulnerability hypothesis"
        finding = Finding(
            fingerprint=f"fp-{uuid.uuid4().hex[:12]}",
            hypothesis=best_hypothesis,
            locations=[FindingLocation(file_path=scoped_paths[0] if scoped_paths else "unknown", start_line=1, end_line=10)],
            supporting_evidence=[e.evidence_id for e in evidences]
        )

        val_result = FindingValidator.validate(finding, self.repo_path)
        if val_result.is_reproducible:
            finding, f_evt = FindingStateMachine.transition(finding, FindingState.CONFIRMED, actor="validator")
            outcome_conf = MemoryConfidence.VALIDATED
        else:
            finding, f_evt = FindingStateMachine.transition(finding, FindingState.REJECTED, actor="validator")
            outcome_conf = MemoryConfidence.REJECTED

        # 8. Record Research Outcome & Project Memory
        research_outcome = ResearchOutcomeRecord(
            project_id=self.project_id,
            task_id=root_task.task_id,
            run_id=child_results[0]["run_id"] if child_results else f"run-{uuid.uuid4().hex[:8]}",
            domain=self.domain,
            hypothesis=best_hypothesis,
            confidence=outcome_conf,
            successful_steps=["precheck", "agent_discovery", "validator"],
            rejected_steps=[] if val_result.is_reproducible else ["validator_reproduction"],
            evidence_refs=[e.evidence_id for e in evidences],
            is_generalizable=val_result.is_reproducible or self.testing_config.get("force_generalizable", False)
        )
        self.memory_service.record_outcome(research_outcome)

        proj_mem = ProjectMemoryRecord(
            project_id=self.project_id,
            task_id=root_task.task_id,
            run_id=research_outcome.run_id,
            domain=self.domain,
            architecture_facts=[f"Target component: {self.target_component}"],
            local_findings=[finding.model_dump()],
            rejected_hypotheses=[] if val_result.is_reproducible else [{"hypothesis": best_hypothesis}],
            successful_strategies=["memory_informed_discovery"],
            failed_strategies=[],
            evidence_refs=[e.evidence_id for e in evidences]
        )
        self.memory_service.record_project_memory(proj_mem)

        # 9. Evaluate for Global Promotion
        prom_rec = self.promotion_engine.evaluate_and_promote(
            outcome=research_outcome,
            title=f"Generalized Pattern for {self.target_component}",
            indicators=precheck_res.findings or ["security_construct", "privilege_check"],
            affected_constructs=[self.target_component],
            validation_method="FindingValidator"
        )

        root_task, complete_evt = TaskStateMachine.transition(root_task, TaskStatus.SUCCEEDED, actor="orchestrator")
        self.task_repo.save(root_task)

        return {
            "workflow_id": self.workflow_id,
            "project_id": self.project_id,
            "root_task_id": root_task.task_id,
            "task_status": "READY_FOR_REVIEW",
            "chosen_agent_count": decision.chosen_agent_count,
            "assigned_agent": child_results[0]["agent_id"] if child_results else None,
            "provider": self.registry.get_agent(child_results[0]["agent_id"]).provider if (child_results and self.registry.get_agent(child_results[0]["agent_id"])) else None,
            "selected_agents": [r["agent_id"] for r in child_results],
            "finding_state": finding.state.value,
            "retrieved_memories_count": len(retrieved_memories),
            "applicable_patterns_count": len(applicable_patterns),
            "validation": {
                "is_reproducible": val_result.is_reproducible,
                "finding_state": finding.state.value,
                "outcome_confidence": outcome_conf.value
            },
            "promotion": {
                "promotion_id": prom_rec.promotion_id,
                "accepted": prom_rec.accepted,
                "pattern_id": prom_rec.pattern_id,
                "rejection_reason": prom_rec.rejection_reason,
                "sanitized_fields": prom_rec.sanitized_fields
            },
            "child_runs": [
                {"agent_id": r["agent_id"], "role": r["role"], "status": r["child_task"].status.value, "workspace": r["workspace"]}
                for r in child_results
            ]
        }
