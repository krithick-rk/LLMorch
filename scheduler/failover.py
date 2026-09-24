"""
LLMorch Failover & Recovery Engine (Phase 5)
Provides durable model-independent checkpoint recovery, quota-aware failover,
run lineage tracking, and loop-prevention agent replacement.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone

from schemas.task import Task, TaskStatus
from schemas.run import Run, RunStatus
from schemas.agent import Agent
from schemas.health import AgentHealthState, AgentQuotaStatus
from schemas.checkpoint import Checkpoint
from schemas.event import Event, EventType
from schemas.errors import ErrorCode, LLMorchError, QuotaExhaustedError, AgentUnavailableError
from schemas.strategy import StrategyDecision, AgentAssignment

from history.database import DatabaseService
from history.repositories import (
    TaskRepository,
    AgentRepository,
    RunRepository,
    EventRepository,
    CheckpointRepository,
    AgentSwitchRepository,
)
from registry.agent_registry import AgentRegistry
from orchestrator.strategy import StrategyEngine
from orchestrator.state_machine import TaskStateMachine
from sandbox.workspace import WorkspaceManager, Workspace

logger = logging.getLogger(__name__)


class FailoverEngine:
    """
    Durable Task Recovery & Agent Failover Manager.
    Handles agent failure classification, state checkpointing, registry health updates,
    loop prevention, model-independent replacement selection, and task resumption.
    """

    def __init__(
        self,
        db_service: DatabaseService,
        registry: AgentRegistry,
        workspace_mgr: WorkspaceManager,
        max_retries_per_task: int = 3
    ):
        self.db = db_service
        self.task_repo = TaskRepository(self.db)
        self.agent_repo = AgentRepository(self.db)
        self.run_repo = RunRepository(self.db)
        self.event_repo = EventRepository(self.db)
        self.chk_repo = CheckpointRepository(self.db)
        self.switch_repo = AgentSwitchRepository(self.db)
        self.registry = registry
        self.workspace_mgr = workspace_mgr
        self.max_retries_per_task = max_retries_per_task
        self.strategy_engine = StrategyEngine(self.registry, config={"max_agents": 4})

    def handle_failure_and_recover(
        self,
        task_id: str,
        failed_run_id: str,
        error_code: ErrorCode,
        failure_reason: str,
        execution_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes complete failover sequence:
        Classify failure -> Update agent health -> Create checkpoint -> Loop prevention ->
        Select replacement -> Spawn new run -> Resume task.
        """
        task = self.task_repo.get(task_id)
        if not task:
            raise LLMorchError(f"Task '{task_id}' not found for recovery", code=ErrorCode.INVALID_STATE_TRANSITION)

        failed_run = self.run_repo.get(failed_run_id) if failed_run_id else None
        failed_agent_id = failed_run.agent_id if failed_run else (task.assigned_agent_id or "unknown")

        # 1. Update Failed Run Status
        if failed_run:
            failed_run.status = RunStatus.TIMEOUT if error_code == ErrorCode.AGENT_TIMEOUT else RunStatus.FAILED
            failed_run.failure_code = error_code.value
            failed_run.failure_reason = failure_reason
            failed_run.end_time = datetime.now(timezone.utc)
            self.run_repo.save(failed_run)

        # 2. Record Failure Events
        self.event_repo.record(Event(
            run_id=failed_run_id,
            event_type=EventType.AGENT_FAILURE_DETECTED,
            actor="failover_engine",
            payload={"task_id": task_id, "failed_agent_id": failed_agent_id, "error_code": error_code.value, "reason": failure_reason}
        ))

        # 3. Update Agent Health in Registry & DB
        agent = self.registry.get_agent(failed_agent_id)
        if agent:
            old_health = agent.health
            if error_code == ErrorCode.QUOTA_EXHAUSTED:
                agent.health = AgentHealthState.QUOTA_LIMITED
                agent.quota_status = AgentQuotaStatus.EXHAUSTED
                agent.availability = False
                self.event_repo.record(Event(event_type=EventType.AGENT_QUOTA_EXHAUSTED, actor="failover_engine", payload={"agent_id": agent.agent_id}))
            elif error_code == ErrorCode.AUTH_FAILURE:
                agent.health = AgentHealthState.AUTH_REQUIRED
                agent.availability = False
            elif error_code in (ErrorCode.AGENT_TIMEOUT, ErrorCode.AGENT_PROCESS_FAILURE, ErrorCode.ADAPTER_FAILURE):
                agent.health = AgentHealthState.UNAVAILABLE
                agent.availability = False
                self.event_repo.record(Event(event_type=EventType.AGENT_MARKED_UNAVAILABLE, actor="failover_engine", payload={"agent_id": agent.agent_id}))

            self.registry.register_agent(agent)
            self.agent_repo.save(agent)

            self.event_repo.record(Event(
                event_type=EventType.AGENT_HEALTH_CHANGED,
                actor="failover_engine",
                payload={"agent_id": agent.agent_id, "old_health": old_health.value, "new_health": agent.health.value}
            ))

        # 4. Check Max Retries Limit
        past_runs = self.run_repo.list_for_task(task_id)
        retry_count = len(past_runs)

        if retry_count > self.max_retries_per_task:
            task, evt = TaskStateMachine.transition(task, TaskStatus.FAILED, actor="failover_engine")
            self.task_repo.save(task)
            self.event_repo.record(Event(
                event_type=EventType.RECOVERY_EXHAUSTED,
                actor="failover_engine",
                payload={"task_id": task_id, "retry_count": retry_count, "limit": self.max_retries_per_task}
            ))
            return {
                "status": "RECOVERY_EXHAUSTED",
                "task_id": task_id,
                "error": "MAX_RETRIES_EXCEEDED",
                "details": f"Task exceeded max recovery retry limit ({self.max_retries_per_task})"
            }

        # 5. Create Immutable Recovery Checkpoint
        ctx = execution_context or {}
        completed = ctx.get("completed_subtasks", ["intake", "precheck"])
        remaining = ctx.get("remaining_subtasks", ["investigation", "validation"])
        artifacts = ctx.get("artifact_refs", [])
        evidences = ctx.get("evidence_refs", [])

        checkpoint = Checkpoint(
            task_id=task_id,
            workflow_id=task.workflow_id,
            run_id=failed_run_id,
            completed_subtasks=completed,
            remaining_subtasks=remaining,
            task_state={"last_known_status": task.status.value, "failed_agent": failed_agent_id},
            artifact_refs=artifacts,
            evidence_refs=evidences,
            workspace_snapshot={"failed_workspace_id": failed_run.workspace_id if failed_run else "unknown"},
            repository_snapshot={"repo_path": ctx.get("repo_path", "")},
            next_action=f"Resume task '{task.objective}' from checkpoint",
            recovery_context={
                "failed_agent_id": failed_agent_id,
                "failure_code": error_code.value,
                "failure_reason": failure_reason,
                "recovery_attempt": retry_count
            },
            is_valid=True
        )
        self.chk_repo.save(checkpoint)
        self.event_repo.record(Event(
            run_id=failed_run_id,
            event_type=EventType.CHECKPOINT_CREATED,
            actor="failover_engine",
            payload={"checkpoint_id": checkpoint.checkpoint_id, "task_id": task_id}
        ))

        # 6. Validate Checkpoint Integrity
        if not checkpoint.is_valid:
            self.event_repo.record(Event(event_type=EventType.RECOVERY_BLOCKED, actor="failover_engine", payload={"checkpoint_id": checkpoint.checkpoint_id, "reason": checkpoint.invalidation_reason}))
            return {
                "status": "RECOVERY_BLOCKED",
                "task_id": task_id,
                "error": "STALE_CHECKPOINT",
                "details": checkpoint.invalidation_reason
            }

        # 7. Loop Prevention & Candidate Filtering
        self.event_repo.record(Event(event_type=EventType.FAILOVER_STARTED, actor="failover_engine", payload={"task_id": task_id}))

        failed_agents_in_chain = [r.agent_id for r in past_runs]

        all_agents = self.registry.list_agents()
        eligible_replacements = [
            a for a in all_agents
            if a.agent_id not in failed_agents_in_chain
            and a.availability
            and a.health == AgentHealthState.AVAILABLE
            and all(cap in a.capabilities for cap in task.required_capabilities)
        ]

        self.event_repo.record(Event(
            event_type=EventType.REPLACEMENT_CANDIDATES_RESOLVED,
            actor="failover_engine",
            payload={"task_id": task_id, "eligible_agent_ids": [a.agent_id for a in eligible_replacements], "excluded_chain": failed_agents_in_chain}
        ))

        if not eligible_replacements:
            task, evt = TaskStateMachine.transition(task, TaskStatus.BLOCKED, actor="failover_engine")
            self.task_repo.save(task)
            self.event_repo.record(Event(
                event_type=EventType.RECOVERY_BLOCKED,
                actor="failover_engine",
                payload={"task_id": task_id, "reason": "No eligible replacement agents available"}
            ))
            return {
                "status": "RECOVERY_BLOCKED",
                "task_id": task_id,
                "error": "NO_ELIGIBLE_REPLACEMENT",
                "details": f"No available replacement agent matching task capabilities (Excluded chain: {failed_agents_in_chain})"
            }

        # Select Replacement Agent
        replacement_agent = eligible_replacements[0]

        self.event_repo.record(Event(
            event_type=EventType.REPLACEMENT_AGENT_SELECTED,
            actor="failover_engine",
            payload={"task_id": task_id, "replacement_agent_id": replacement_agent.agent_id, "previous_agent_id": failed_agent_id}
        ))

        # 8. Create Replacement Run & Link Lineage
        new_workspace_id = f"ws-recovery-{task_id}-{replacement_agent.agent_id[:6]}"
        new_run = Run(
            task_id=task_id,
            parent_run_id=failed_run_id,
            agent_id=replacement_agent.agent_id,
            workspace_id=new_workspace_id,
            environment_fingerprint=failed_run.environment_fingerprint if failed_run else "recovery_env",
            status=RunStatus.RUNNING
        )
        self.run_repo.save(new_run)

        # 9. Update Task & Resume State Machine
        task.assigned_agent_id = replacement_agent.agent_id
        task.retry_count = retry_count
        if task.status != TaskStatus.RUNNING:
            if task.status == TaskStatus.QUEUED:
                task, _ = TaskStateMachine.transition(task, TaskStatus.DISPATCHED, actor="failover_engine")
            task, resume_evt = TaskStateMachine.transition(task, TaskStatus.RUNNING, actor="failover_engine")
        self.task_repo.save(task)

        self.event_repo.record(Event(
            run_id=new_run.run_id,
            event_type=EventType.TASK_REASSIGNED,
            actor="failover_engine",
            payload={"task_id": task_id, "new_agent_id": replacement_agent.agent_id, "old_agent_id": failed_agent_id}
        ))
        self.event_repo.record(Event(
            run_id=new_run.run_id,
            event_type=EventType.TASK_RESUMED,
            actor="failover_engine",
            payload={"task_id": task_id, "checkpoint_id": checkpoint.checkpoint_id}
        ))

        if hasattr(self.registry, "record_failover"):
            self.registry.record_failover(failed_agent_id)

        switch_rec = self.switch_repo.record_switch(
            task_id=task_id,
            run_id=new_run.run_id,
            previous_agent_id=failed_agent_id,
            new_agent_id=replacement_agent.agent_id,
            reason=failure_reason,
            switch_type="FAILOVER",
            checkpoint_id=checkpoint.checkpoint_id,
            resume_action="RESUME"
        )

        self.event_repo.record(Event(
            run_id=new_run.run_id,
            event_type=EventType.AGENT_FAILOVER_COMPLETED,
            actor="failover_engine",
            payload={
                "task_id": task_id,
                "failed_agent_id": failed_agent_id,
                "replacement_agent_id": replacement_agent.agent_id,
                "checkpoint_id": checkpoint.checkpoint_id,
                "switch_id": switch_rec["switch_id"]
            }
        ))

        return {
            "status": "RESUMED",
            "task_id": task_id,
            "failed_run_id": failed_run_id,
            "replacement_run_id": new_run.run_id,
            "replacement_agent_id": replacement_agent.agent_id,
            "checkpoint_id": checkpoint.checkpoint_id,
            "recovery_attempt": retry_count
        }

    def list_recovery_history(self, task_id: str) -> Dict[str, Any]:
        """
        Returns complete audit trail of runs, checkpoints, and recovery events for a task.
        """
        runs = self.run_repo.list_for_task(task_id)
        checkpoints = self.chk_repo.list_for_task(task_id)

        history_items = []
        for run in runs:
            events = self.event_repo.list_for_run(run.run_id)
            history_items.append({
                "run_id": run.run_id,
                "parent_run_id": run.parent_run_id,
                "agent_id": run.agent_id,
                "status": run.status.value,
                "failure_code": run.failure_code,
                "failure_reason": run.failure_reason,
                "start_time": run.start_time.isoformat(),
                "end_time": run.end_time.isoformat() if run.end_time else None,
                "event_count": len(events)
            })

        return {
            "task_id": task_id,
            "run_lineage": history_items,
            "checkpoints": [
                {
                    "checkpoint_id": c.checkpoint_id,
                    "run_id": c.run_id,
                    "created_at": c.created_at.isoformat(),
                    "next_action": c.next_action,
                    "recovery_context": c.recovery_context,
                    "is_valid": c.is_valid
                }
                for c in checkpoints
            ]
        }
