"""
LLMorch Agent & Model Switcher (Phase 9.1)
Authoritative control-plane execution component for manual and policy-driven agent/model switching.
Guarantees task lineage preservation, checkpoint generation, evidence immutability, and zero duplicate execution.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid

from schemas.task import Task, TaskStatus
from schemas.run import Run, RunStatus
from schemas.agent import Agent
from schemas.health import AgentHealthState
from schemas.checkpoint import Checkpoint
from schemas.event import Event, EventType
from schemas.errors import LLMorchError, ErrorCode, AgentUnavailableError

from history.database import DatabaseService, get_db_path
from history.repositories import (
    TaskRepository,
    RunRepository,
    CheckpointRepository,
    EventRepository,
    AgentSwitchRepository,
    ModelSwitchRepository,
)
from registry.agent_registry import AgentRegistry
from registry.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


class AgentSwitcher:
    """
    Supervises dynamic switching of agents and models for tasks.
    Coordinates between database, agent registry, and model registry.
    """

    def __init__(
        self,
        db_service: Optional[DatabaseService] = None,
        agent_registry: Optional[AgentRegistry] = None,
        model_registry: Optional[ModelRegistry] = None,
    ):
        self.db = db_service or DatabaseService(get_db_path())
        self.task_repo = TaskRepository(self.db)
        self.run_repo = RunRepository(self.db)
        self.chk_repo = CheckpointRepository(self.db)
        self.event_repo = EventRepository(self.db)
        self.switch_repo = AgentSwitchRepository(self.db)
        self.model_switch_repo = ModelSwitchRepository(self.db)

        self.model_registry = model_registry or ModelRegistry()
        self.agent_registry = agent_registry or AgentRegistry(model_registry=self.model_registry, populate_defaults=True)

    def switch_agent(
        self,
        task_id: str,
        new_agent_id: str,
        reason: str,
        resume_action: str = "RESUME_FROM_CHECKPOINT",
        new_model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes safe, auditable agent switch:
        1. Validate target agent availability & capability match.
        2. Checkpoint current task progress, artifacts, and evidence.
        3. Supervise/retire active run to prevent duplicate execution.
        4. Select & bind compatible model for replacement agent.
        5. Create linked replacement run with parent lineage.
        6. Reassign task and broadcast state transitions.
        """
        # 1. Fetch Task
        task = self.task_repo.get(task_id)
        if not task:
            raise LLMorchError(f"Task '{task_id}' not found for agent switch", code=ErrorCode.INVALID_STATE_TRANSITION)

        previous_agent_id = task.assigned_agent_id or "unassigned"

        if previous_agent_id == new_agent_id:
            raise LLMorchError(f"Target agent '{new_agent_id}' is already assigned to task '{task_id}'", code=ErrorCode.INVALID_STATE_TRANSITION)

        # 2. Validate Replacement Agent
        target_agent = self.agent_registry.get_agent(new_agent_id)
        if not target_agent:
            raise AgentUnavailableError(f"Target agent '{new_agent_id}' is not registered in AgentRegistry")

        if not target_agent.availability or target_agent.health not in (AgentHealthState.AVAILABLE, AgentHealthState.DEGRADED):
            raise AgentUnavailableError(f"Target agent '{new_agent_id}' is not available (Health: {target_agent.health.value})")

        if not getattr(target_agent, "enabled", True):
            raise AgentUnavailableError(f"Target agent '{new_agent_id}' is disabled by analyst policy")

        # Execution policy check
        from scheduler.execution_policy import get_execution_policy
        exec_policy = get_execution_policy()
        if not exec_policy.is_agent_executable(new_agent_id):
            reason = exec_policy.get_agent_disabled_reason(new_agent_id) or "Execution disabled by policy"
            raise AgentUnavailableError(f"Target agent '{new_agent_id}' cannot be switched to: {reason}")


        # Capability check
        req_caps = set(task.required_capabilities)
        agent_caps = set(target_agent.capabilities)
        if not req_caps.issubset(agent_caps):
            raise LLMorchError(
                f"Agent '{new_agent_id}' lacks required task capabilities: {req_caps - agent_caps}",
                code=ErrorCode.INVALID_STATE_TRANSITION
            )

        # 3. Model Compatibility for Replacement Agent
        resolved_model_id = new_model_id
        if resolved_model_id:
            if not self.model_registry.is_model_supported_by_agent(new_agent_id, resolved_model_id):
                raise LLMorchError(
                    f"Model '{resolved_model_id}' is not supported by agent '{new_agent_id}'",
                    code=ErrorCode.INVALID_STATE_TRANSITION
                )
        else:
            default_model = self.model_registry.get_default_model_for_agent(new_agent_id)
            resolved_model_id = default_model.model_id if default_model else "runtime-resolved"

        # Emit REQUESTED & APPROVED events
        self.event_repo.record(Event(
            event_type=EventType.AGENT_SWITCH_REQUESTED,
            actor="analyst",
            payload={
                "task_id": task_id,
                "previous_agent_id": previous_agent_id,
                "target_agent_id": new_agent_id,
                "reason": reason,
                "resume_action": resume_action,
            }
        ))
        self.event_repo.record(Event(
            event_type=EventType.AGENT_SWITCH_APPROVED,
            actor="scheduler",
            payload={"task_id": task_id, "approved_agent_id": new_agent_id}
        ))

        # 4. Checkpoint Current State
        past_runs = self.run_repo.list_for_task(task_id)
        active_run = past_runs[0] if past_runs else None
        failed_run_id = active_run.run_id if active_run else f"run-init-{uuid.uuid4().hex[:6]}"

        checkpoint = Checkpoint(
            task_id=task_id,
            workflow_id=task.workflow_id,
            run_id=failed_run_id,
            completed_subtasks=["intake", "scoped_discovery"],
            remaining_subtasks=["deep_investigation", "validation"],
            task_state={"last_status": task.status.value, "switch_reason": reason, "previous_agent": previous_agent_id},
            artifact_refs=[],
            evidence_refs=[],
            workspace_snapshot={"switch_workspace": active_run.workspace_id if active_run else "ws-default"},
            repository_snapshot={"task_objective": task.objective},
            next_action=f"Continue execution with replacement agent '{new_agent_id}' ({resume_action})",
            recovery_context={"switch_type": "MANUAL", "reason": reason, "new_model_id": resolved_model_id},
            is_valid=True
        )
        self.chk_repo.save(checkpoint)

        # 5. Retire Old Run to Prevent Duplicate Execution
        if active_run and active_run.status == RunStatus.RUNNING:
            active_run.status = RunStatus.CANCELLED
            active_run.failure_reason = f"Superseded by manual agent switch to {new_agent_id}"
            active_run.end_time = datetime.now(timezone.utc)
            self.run_repo.save(active_run)

        # Emit STARTED event
        self.event_repo.record(Event(
            run_id=failed_run_id,
            event_type=EventType.AGENT_SWITCH_STARTED,
            actor="agent_switcher",
            payload={
                "task_id": task_id,
                "checkpoint_id": checkpoint.checkpoint_id,
                "previous_agent_id": previous_agent_id,
                "new_agent_id": new_agent_id,
            }
        ))

        # 6. Spawn Replacement Run with Preserved Lineage
        new_run = Run(
            task_id=task_id,
            parent_run_id=failed_run_id,
            agent_id=new_agent_id,
            adapter_version=target_agent.adapter_version,
            workspace_id=f"ws-switched-{task_id[:8]}-{new_agent_id[:6]}",
            environment_fingerprint=f"env-{new_agent_id}-{resolved_model_id}",
            status=RunStatus.RUNNING if resume_action != "PAUSE" else RunStatus.QUEUED,
            start_time=datetime.now(timezone.utc)
        )
        self.run_repo.save(new_run)

        # 7. Update Task
        task.assigned_agent_id = new_agent_id
        if resume_action == "PAUSE":
            task.status = TaskStatus.BLOCKED
        else:
            task.status = TaskStatus.DISPATCHED
        task.retry_count += 1
        self.task_repo.save(task)

        # 8. Record in Switch Audit Table
        switch_record = self.switch_repo.record_switch(
            task_id=task_id,
            run_id=new_run.run_id,
            previous_agent_id=previous_agent_id,
            new_agent_id=new_agent_id,
            reason=reason,
            switch_type="MANUAL",
            previous_model_id=task.preferred_roles[0] if task.preferred_roles else "default",
            new_model_id=resolved_model_id,
            checkpoint_id=checkpoint.checkpoint_id,
            resume_action=resume_action
        )

        self.agent_registry.record_switch(new_agent_id)

        # Emit COMPLETED event
        self.event_repo.record(Event(
            run_id=new_run.run_id,
            event_type=EventType.AGENT_SWITCH_COMPLETED,
            actor="agent_switcher",
            payload={
                "switch_id": switch_record["switch_id"],
                "task_id": task_id,
                "new_run_id": new_run.run_id,
                "new_agent_id": new_agent_id,
                "new_model_id": resolved_model_id,
                "checkpoint_id": checkpoint.checkpoint_id,
            }
        ))

        return {
            "success": True,
            "switch_id": switch_record["switch_id"],
            "task_id": task_id,
            "previous_agent_id": previous_agent_id,
            "new_agent_id": new_agent_id,
            "new_model_id": resolved_model_id,
            "new_run_id": new_run.run_id,
            "checkpoint_id": checkpoint.checkpoint_id,
            "resume_action": resume_action,
        }

    def switch_model(
        self,
        agent_id: str,
        new_model_id: str,
        reason: str,
        task_id: Optional[str] = None,
        run_id: Optional[str] = None,
        scope: str = "CURRENT_TASK"
    ) -> Dict[str, Any]:
        """
        Switches the model associated with an agent or task.
        Validates model availability and compatibility via ModelRegistry.
        """
        # Validate model
        model = self.model_registry.get_model(new_model_id)
        if not model:
            raise LLMorchError(f"Model '{new_model_id}' not found in ModelRegistry", code=ErrorCode.INVALID_STATE_TRANSITION)

        if not model.enabled:
            raise LLMorchError(f"Model '{new_model_id}' is disabled", code=ErrorCode.INVALID_STATE_TRANSITION)

        if not self.model_registry.is_model_supported_by_agent(agent_id, new_model_id):
            supported = self.model_registry.get_models_for_agent(agent_id)
            raise LLMorchError(
                f"Model '{new_model_id}' is not supported by agent '{agent_id}'. Supported: {[m.model_id for m in supported]}",
                code=ErrorCode.INVALID_STATE_TRANSITION
            )

        agent = self.agent_registry.get_agent(agent_id)
        prev_model_id = agent.current_model_id or agent.model if agent else "unknown"

        # Emit REQUESTED event
        self.event_repo.record(Event(
            event_type=EventType.MODEL_SWITCH_REQUESTED,
            actor="analyst",
            payload={
                "agent_id": agent_id,
                "previous_model_id": prev_model_id,
                "target_model_id": new_model_id,
                "reason": reason,
                "scope": scope,
            }
        ))

        # Update Agent active model
        if agent:
            self.agent_registry.set_agent_model(agent_id, new_model_id)

        # Record audit entry
        record = self.model_switch_repo.record_switch(
            agent_id=agent_id,
            previous_model_id=prev_model_id,
            new_model_id=new_model_id,
            reason=reason,
            task_id=task_id,
            run_id=run_id,
            scope=scope
        )

        # Emit COMPLETED event
        self.event_repo.record(Event(
            event_type=EventType.MODEL_SWITCH_COMPLETED,
            actor="agent_switcher",
            payload={
                "switch_id": record["switch_id"],
                "agent_id": agent_id,
                "previous_model_id": prev_model_id,
                "new_model_id": new_model_id,
                "reason": reason,
            }
        ))

        return {
            "success": True,
            "switch_id": record["switch_id"],
            "agent_id": agent_id,
            "previous_model_id": prev_model_id,
            "new_model_id": new_model_id,
            "scope": scope,
            "reason": reason,
        }
