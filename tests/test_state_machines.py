"""
Unit Tests - Task & Finding State Machines
"""

import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.task import Task, TaskStatus
from schemas.finding import Finding, FindingState
from schemas.errors import InvalidStateTransitionError
from orchestrator.state_machine import TaskStateMachine, FindingStateMachine


def test_task_state_machine_legal_flow():
    task = Task(objective="Perform code audit")
    assert task.status == TaskStatus.QUEUED

    # QUEUED -> DISPATCHED
    task, evt1 = TaskStateMachine.transition(task, TaskStatus.DISPATCHED, actor="orchestrator")
    assert task.status == TaskStatus.DISPATCHED
    assert evt1.payload["from_state"] == "QUEUED"
    assert evt1.payload["to_state"] == "DISPATCHED"

    # DISPATCHED -> RUNNING
    task, evt2 = TaskStateMachine.transition(task, TaskStatus.RUNNING, actor="agent-agy-01")
    assert task.status == TaskStatus.RUNNING
    assert task.started_at is not None

    # RUNNING -> SUCCEEDED
    task, evt3 = TaskStateMachine.transition(task, TaskStatus.SUCCEEDED, actor="orchestrator")
    assert task.status == TaskStatus.SUCCEEDED
    assert task.completed_at is not None


def test_task_state_machine_illegal_transition():
    task = Task(objective="Perform code audit")
    with pytest.raises(InvalidStateTransitionError):
        # QUEUED directly to SUCCEEDED is illegal
        TaskStateMachine.transition(task, TaskStatus.SUCCEEDED)


def test_task_terminal_lock():
    task = Task(objective="Perform code audit")
    task, _ = TaskStateMachine.transition(task, TaskStatus.DISPATCHED)
    task, _ = TaskStateMachine.transition(task, TaskStatus.FAILED)

    with pytest.raises(InvalidStateTransitionError):
        # Cannot transition out of terminal state FAILED
        TaskStateMachine.transition(task, TaskStatus.RUNNING)


def test_finding_state_machine_flow():
    finding = Finding(fingerprint="fp-001", hypothesis="Unchecked pointer dereference")
    assert finding.state == FindingState.HYPOTHESIS

    finding, _ = FindingStateMachine.transition(finding, FindingState.REVIEWED)
    assert finding.state == FindingState.REVIEWED

    finding, _ = FindingStateMachine.transition(finding, FindingState.VALIDATION_PENDING)
    assert finding.state == FindingState.VALIDATION_PENDING

    finding, _ = FindingStateMachine.transition(finding, FindingState.CONFIRMED)
    assert finding.state == FindingState.CONFIRMED

    with pytest.raises(InvalidStateTransitionError):
        # CONFIRMED is terminal
        FindingStateMachine.transition(finding, FindingState.REJECTED)


if __name__ == "__main__":
    pytest.main([__file__])
