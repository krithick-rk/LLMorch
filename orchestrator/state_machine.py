"""
LLMorch Orchestrator State Machines
Enforces valid state transitions for Task and Finding models and produces structured audit Events.
"""

from typing import Dict, Set, Tuple
from datetime import datetime, timezone
from schemas.task import Task, TaskStatus
from schemas.finding import Finding, FindingState
from schemas.event import Event, EventType
from schemas.errors import InvalidStateTransitionError


class TaskStateMachine:
    """
    Task State Machine.
    Validates state transition legality and produces STATE_TRANSITION Events.
    """
    LEGAL_TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
        TaskStatus.QUEUED: {TaskStatus.DISPATCHED, TaskStatus.BLOCKED, TaskStatus.FAILED, TaskStatus.CANCELED},
        TaskStatus.DISPATCHED: {TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELED},
        TaskStatus.RUNNING: {TaskStatus.WAITING, TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELED, TaskStatus.BLOCKED},
        TaskStatus.WAITING: {TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELED},
        TaskStatus.BLOCKED: {TaskStatus.RUNNING, TaskStatus.QUEUED, TaskStatus.FAILED, TaskStatus.CANCELED},
        TaskStatus.SUCCEEDED: set(),  # Terminal
        TaskStatus.FAILED: set(),     # Terminal
        TaskStatus.CANCELED: set(),   # Terminal
    }

    TERMINAL_STATES: Set[TaskStatus] = {
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED,
        TaskStatus.CANCELED,
    }

    @classmethod
    def can_transition(cls, current: TaskStatus, target: TaskStatus) -> bool:
        return target in cls.LEGAL_TRANSITIONS.get(current, set())

    @classmethod
    def transition(cls, task: Task, new_status: TaskStatus, actor: str = "orchestrator", reason: str = "") -> Tuple[Task, Event]:
        """
        Executes a state transition on a Task object if legal.
        Returns updated Task and generated Event.
        """
        if task.status in cls.TERMINAL_STATES:
            raise InvalidStateTransitionError(
                f"Cannot transition task {task.task_id} out of terminal state '{task.status}' to '{new_status}'"
            )

        if not cls.can_transition(task.status, new_status):
            raise InvalidStateTransitionError(
                f"Illegal Task state transition from '{task.status}' to '{new_status}' for task {task.task_id}"
            )

        old_status = task.status
        task.status = new_status
        now = datetime.now(timezone.utc)

        if new_status == TaskStatus.RUNNING and task.started_at is None:
            task.started_at = now
        elif new_status in cls.TERMINAL_STATES:
            task.completed_at = now

        event_type = EventType.STATE_TRANSITION
        if new_status == TaskStatus.DISPATCHED:
            event_type = EventType.TASK_DISPATCHED
        elif new_status == TaskStatus.SUCCEEDED or new_status == TaskStatus.FAILED:
            event_type = EventType.TASK_COMPLETED

        event = Event(
            event_type=event_type,
            actor=actor,
            payload={
                "task_id": task.task_id,
                "from_state": old_status.value,
                "to_state": new_status.value,
                "reason": reason,
            }
        )

        return task, event


class FindingStateMachine:
    """
    Finding State Machine.
    The orchestrator owns state transitions for findings/hypotheses.
    """
    LEGAL_TRANSITIONS: Dict[FindingState, Set[FindingState]] = {
        FindingState.HYPOTHESIS: {FindingState.REVIEWED, FindingState.VALIDATION_PENDING, FindingState.REJECTED},
        FindingState.REVIEWED: {FindingState.CORROBORATED, FindingState.CONTRADICTED, FindingState.VALIDATION_PENDING, FindingState.REJECTED},
        FindingState.CORROBORATED: {FindingState.VALIDATION_PENDING, FindingState.CONFIRMED, FindingState.UNRESOLVED},
        FindingState.CONTRADICTED: {FindingState.REJECTED, FindingState.UNRESOLVED},
        FindingState.VALIDATION_PENDING: {FindingState.CONFIRMED, FindingState.REJECTED, FindingState.CONTRADICTED, FindingState.UNRESOLVED},
        FindingState.UNRESOLVED: {FindingState.VALIDATION_PENDING, FindingState.REVIEWED, FindingState.REJECTED},
        FindingState.CONFIRMED: set(), # Terminal
        FindingState.REJECTED: set(),  # Terminal
    }

    TERMINAL_STATES: Set[FindingState] = {
        FindingState.CONFIRMED,
        FindingState.REJECTED,
    }

    @classmethod
    def can_transition(cls, current: FindingState, target: FindingState) -> bool:
        return target in cls.LEGAL_TRANSITIONS.get(current, set())

    @classmethod
    def transition(cls, finding: Finding, new_state: FindingState, actor: str = "orchestrator", reason: str = "") -> Tuple[Finding, Event]:
        if finding.state in cls.TERMINAL_STATES:
            raise InvalidStateTransitionError(
                f"Cannot transition finding {finding.finding_id} out of terminal state '{finding.state}' to '{new_state}'"
            )

        if not cls.can_transition(finding.state, new_state):
            raise InvalidStateTransitionError(
                f"Illegal Finding state transition from '{finding.state}' to '{new_state}' for finding {finding.finding_id}"
            )

        old_state = finding.state
        finding.state = new_state
        finding.timestamps["updated_at"] = datetime.now(timezone.utc)
        if new_state in cls.TERMINAL_STATES:
            finding.timestamps["finalized_at"] = datetime.now(timezone.utc)

        event = Event(
            event_type=EventType.STATE_TRANSITION,
            actor=actor,
            payload={
                "finding_id": finding.finding_id,
                "from_state": old_state.value,
                "to_state": new_state.value,
                "reason": reason,
            }
        )

        return finding, event
