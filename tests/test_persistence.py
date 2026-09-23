"""
Unit Tests - SQLite Persistence & Repositories
Verifies foreign keys, CRUD operations, transactions, and event/checkpoint persistence.
"""

import pytest
import sys
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from history.database import DatabaseService
from history.repositories import (
    TaskRepository,
    AgentRepository,
    RunRepository,
    CheckpointRepository,
    EventRepository,
)
from schemas.task import Task, TaskStatus
from schemas.agent import Agent, AgentInterface
from schemas.run import Run, RunStatus
from schemas.checkpoint import Checkpoint
from schemas.event import Event, EventType


def test_sqlite_foreign_key_enforcement():
    db = DatabaseService(":memory:")
    run_repo = RunRepository(db)

    # Attempting to save a Run with non-existent task_id should raise IntegrityError
    run = Run(
        task_id="non-existent-task",
        agent_id="non-existent-agent",
        workspace_id="ws-1",
        environment_fingerprint="env-1"
    )

    with pytest.raises(sqlite3.IntegrityError):
        run_repo.save(run)


def test_task_repository_crud():
    db = DatabaseService(":memory:")
    repo = TaskRepository(db)

    task = Task(objective="Static analysis of Caliptra IP")
    repo.save(task)

    retrieved = repo.get(task.task_id)
    assert retrieved is not None
    assert retrieved.objective == task.objective
    assert retrieved.status == TaskStatus.QUEUED


def test_run_and_event_persistence():
    db = DatabaseService(":memory:")
    task_repo = TaskRepository(db)
    agent_repo = AgentRepository(db)
    run_repo = RunRepository(db)
    event_repo = EventRepository(db)

    task = Task(objective="Fuzzing task")
    task_repo.save(task)

    agent = Agent(agent_id="agent-agy-01", provider="antigravity", interface=AgentInterface.CLI)
    agent_repo.save(agent)

    run = Run(
        task_id=task.task_id,
        agent_id=agent.agent_id,
        workspace_id="ws-1",
        environment_fingerprint="env-1"
    )
    run_repo.save(run)

    event = Event(
        run_id=run.run_id,
        event_type=EventType.AGENT_STARTED,
        actor=agent.agent_id,
        payload={"message": "Started fuzzing"}
    )
    event_repo.record(event)

    events = event_repo.list_for_run(run.run_id)
    assert len(events) == 1
    assert events[0].actor == "agent-agy-01"


def test_checkpoint_persistence():
    db = DatabaseService(":memory:")
    task_repo = TaskRepository(db)
    chk_repo = CheckpointRepository(db)

    task = Task(objective="Multi-step analysis")
    task_repo.save(task)

    chk = Checkpoint(
        task_id=task.task_id,
        completed_subtasks=["step-1", "step-2"],
        remaining_subtasks=["step-3"],
        next_action="Run static analysis on step-3"
    )
    chk_repo.save(chk)

    retrieved = chk_repo.get_latest_for_task(task.task_id)
    assert retrieved is not None
    assert retrieved.completed_subtasks == ["step-1", "step-2"]
    assert retrieved.next_action == "Run static analysis on step-3"


if __name__ == "__main__":
    pytest.main([__file__])
