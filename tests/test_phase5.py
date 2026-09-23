"""
Unit & Integration Tests - Phase 5 Failover, Quota & Checkpoint Recovery
"""

import pytest
import sys
import os
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.task import Task, TaskStatus, RiskLevel
from schemas.agent import Agent, AgentInterface
from schemas.health import AgentHealthState, AgentQuotaStatus
from schemas.checkpoint import Checkpoint
from schemas.run import Run, RunStatus
from schemas.errors import ErrorCode
from registry.agent_registry import AgentRegistry
from scheduler.failover import FailoverEngine
from sandbox.workspace import WorkspaceManager
from history.database import DatabaseService
from history.repositories import TaskRepository, RunRepository, CheckpointRepository, EventRepository
from orchestrator.investigation import InvestigationWorkflow


@pytest.fixture
def db():
    return DatabaseService(":memory:")


@pytest.fixture
def registry():
    reg = AgentRegistry()
    reg.register_agent(Agent(agent_id="agent-agy-01", provider="antigravity", interface=AgentInterface.CLI, capabilities=["repository_analysis", "security_review"], health=AgentHealthState.AVAILABLE, availability=True))
    reg.register_agent(Agent(agent_id="agent-claude-01", provider="anthropic", interface=AgentInterface.CLI, capabilities=["repository_analysis", "security_review"], health=AgentHealthState.AVAILABLE, availability=True))
    reg.register_agent(Agent(agent_id="agent-codex-01", provider="openai", interface=AgentInterface.CLI, capabilities=["repository_analysis", "security_review"], health=AgentHealthState.AVAILABLE, availability=True))
    return reg


def test_agent_process_crash_failover(db, registry):
    workspace_mgr = WorkspaceManager()
    engine = FailoverEngine(db, registry, workspace_mgr)

    task_repo = TaskRepository(db)
    run_repo = RunRepository(db)

    task = Task(objective="Investigate auth bug", required_capabilities=["repository_analysis", "security_review"], assigned_agent_id="agent-agy-01")
    task_repo.save(task)

    run1 = Run(task_id=task.task_id, agent_id="agent-agy-01", workspace_id="ws-1", environment_fingerprint="env1", status=RunStatus.RUNNING)
    run_repo.save(run1)

    result = engine.handle_failure_and_recover(
        task_id=task.task_id,
        failed_run_id=run1.run_id,
        error_code=ErrorCode.AGENT_PROCESS_FAILURE,
        failure_reason="Process crashed unexpectedly with exit code 139"
    )

    assert result["status"] == "RESUMED"
    assert result["replacement_agent_id"] == "agent-claude-01"
    assert result["replacement_run_id"] != run1.run_id

    updated_run1 = run_repo.get(run1.run_id)
    assert updated_run1.status == RunStatus.FAILED
    assert updated_run1.failure_code == ErrorCode.AGENT_PROCESS_FAILURE.value

    run2 = run_repo.get(result["replacement_run_id"])
    assert run2.parent_run_id == run1.run_id
    assert run2.agent_id == "agent-claude-01"


def test_agent_timeout_failover(db, registry):
    engine = FailoverEngine(db, registry, WorkspaceManager())
    task_repo, run_repo = TaskRepository(db), RunRepository(db)

    task = Task(objective="Investigate timeout bug", required_capabilities=["repository_analysis", "security_review"], assigned_agent_id="agent-agy-01")
    task_repo.save(task)

    run1 = Run(task_id=task.task_id, agent_id="agent-agy-01", workspace_id="ws-1", environment_fingerprint="env1")
    run_repo.save(run1)

    result = engine.handle_failure_and_recover(
        task_id=task.task_id,
        failed_run_id=run1.run_id,
        error_code=ErrorCode.AGENT_TIMEOUT,
        failure_reason="Execution exceeded timeout threshold of 300s"
    )

    assert result["status"] == "RESUMED"
    assert result["replacement_agent_id"] == "agent-claude-01"

    updated_run1 = run_repo.get(run1.run_id)
    assert updated_run1.status == RunStatus.TIMEOUT


def test_simulated_quota_exhaustion(db, registry):
    engine = FailoverEngine(db, registry, WorkspaceManager())
    task_repo, run_repo = TaskRepository(db), RunRepository(db)

    task = Task(objective="Quota test", required_capabilities=["repository_analysis", "security_review"], assigned_agent_id="agent-agy-01")
    task_repo.save(task)

    run1 = Run(task_id=task.task_id, agent_id="agent-agy-01", workspace_id="ws-1", environment_fingerprint="env1")
    run_repo.save(run1)

    result = engine.handle_failure_and_recover(
        task_id=task.task_id,
        failed_run_id=run1.run_id,
        error_code=ErrorCode.QUOTA_EXHAUSTED,
        failure_reason="API key rate limit 429 quota exhausted"
    )

    assert result["status"] == "RESUMED"
    assert result["replacement_agent_id"] == "agent-claude-01"

    agy_agent = registry.get_agent("agent-agy-01")
    assert agy_agent.health == AgentHealthState.QUOTA_LIMITED
    assert agy_agent.availability is False


def test_loop_prevention(db, registry):
    engine = FailoverEngine(db, registry, WorkspaceManager())
    task_repo, run_repo = TaskRepository(db), RunRepository(db)

    task = Task(objective="Loop prevention test", required_capabilities=["repository_analysis", "security_review"], assigned_agent_id="agent-agy-01")
    task_repo.save(task)

    # Attempt 1 (AGY fails)
    run1 = Run(task_id=task.task_id, agent_id="agent-agy-01", workspace_id="ws-1", environment_fingerprint="env1")
    run_repo.save(run1)
    engine.handle_failure_and_recover(task.task_id, run1.run_id, ErrorCode.AGENT_PROCESS_FAILURE, "Crash 1")

    # Attempt 2 (Claude fails)
    run2 = Run(task_id=task.task_id, parent_run_id=run1.run_id, agent_id="agent-claude-01", workspace_id="ws-2", environment_fingerprint="env1")
    run_repo.save(run2)
    res2 = engine.handle_failure_and_recover(task.task_id, run2.run_id, ErrorCode.AGENT_PROCESS_FAILURE, "Crash 2")

    # Codex should be selected next (AGY and Claude are in recovery chain and excluded!)
    assert res2["status"] == "RESUMED"
    assert res2["replacement_agent_id"] == "agent-codex-01"


def test_no_eligible_replacement(db):
    single_reg = AgentRegistry()
    single_reg.register_agent(Agent(agent_id="agent-only-one", provider="antigravity", interface=AgentInterface.CLI, capabilities=["security_review"], health=AgentHealthState.AVAILABLE, availability=True))

    engine = FailoverEngine(db, single_reg, WorkspaceManager())
    task_repo, run_repo = TaskRepository(db), RunRepository(db)

    task = Task(objective="Only agent test", required_capabilities=["security_review"], assigned_agent_id="agent-only-one")
    task_repo.save(task)

    run1 = Run(task_id=task.task_id, agent_id="agent-only-one", workspace_id="ws-1", environment_fingerprint="env1")
    run_repo.save(run1)

    result = engine.handle_failure_and_recover(task.task_id, run1.run_id, ErrorCode.AGENT_PROCESS_FAILURE, "Single agent crashed")

    assert result["status"] == "RECOVERY_BLOCKED"
    assert result["error"] == "NO_ELIGIBLE_REPLACEMENT"

    updated_task = task_repo.get(task.task_id)
    assert updated_task.status == TaskStatus.BLOCKED


def test_max_retries_exceeded(db, registry):
    engine = FailoverEngine(db, registry, WorkspaceManager(), max_retries_per_task=2)
    task_repo, run_repo = TaskRepository(db), RunRepository(db)

    task = Task(objective="Max retry test", required_capabilities=["security_review"], assigned_agent_id="agent-agy-01")
    task_repo.save(task)

    # 3 past runs > max_retries_per_task (2)
    for i in range(3):
        r = Run(task_id=task.task_id, agent_id=f"agent-0{i+1}", workspace_id=f"ws-{i}", environment_fingerprint="env")
        run_repo.save(r)

    result = engine.handle_failure_and_recover(task.task_id, "run-dummy", ErrorCode.AGENT_PROCESS_FAILURE, "Exceeding retries")

    assert result["status"] == "RECOVERY_EXHAUSTED"
    assert task_repo.get(task.task_id).status == TaskStatus.FAILED


def test_stale_checkpoint_detection(db, registry):
    engine = FailoverEngine(db, registry, WorkspaceManager())
    chk_repo = CheckpointRepository(db)

    chk = Checkpoint(task_id="task-stale", run_id="run-stale", completed_subtasks=[], remaining_subtasks=[], is_valid=False, invalidation_reason="Workspace directory deleted")
    chk_repo.save(chk)

    retrieved = chk_repo.get_latest_for_task("task-stale")
    assert retrieved.is_valid is False
    assert retrieved.invalidation_reason == "Workspace directory deleted"


def test_controlled_real_failover_execution():
    db = DatabaseService(":memory:")
    wf = InvestigationWorkflow(
        repo_path=str(PROJECT_ROOT),
        target_component="schemas",
        testing_config={"simulate_quota_exhaustion_for": ["agent-agy-01"]},
        db_service=db
    )
    result = wf.run()

    assert result["task_status"] == "READY_FOR_REVIEW"
    assert "agent-claude-01" in result["selected_agents"] or "agent-codex-01" in result["selected_agents"]


if __name__ == "__main__":
    pytest.main([__file__])
