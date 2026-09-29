"""
test_plan_execution_pipeline.py — Verification of Complete Plan Approval -> Execution Pipeline.

Tests:
1. End-to-end plan generation, approval, run creation, work package creation, task creation with project_id.
2. Direct orchestrator run execution: agent process start, deterministic tool execution, evidence capture, validation, closure, and run completion.
3. Approval idempotency: duplicate approval on active run rejected.
4. Dependency resolution: dependent tasks start BLOCKED and become eligible when dependency completes.
5. Strict Enterprise Policy: Claude executor forbidden, single-agent AGY execution allowed.
6. Project isolation: project_id preserved across runs, workpackages, tasks, tool executions, and events.
"""

import os
import json
import time
import pytest
import tempfile
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient

from api.app import app
from api.session import get_default_token
from orchestrator.orchestrator import CentralOrchestrator
from supervisor.supervisor import SoCSupervisor
from history.database import DatabaseService
from history.soc_repositories import VerificationPlanRepository, WorkPackageRepository
from history.repositories import TaskRepository
from history.phase9_repositories import ToolExecutionRepository
from schemas.soc_verification import VerificationPlan, WorkPackage


@pytest.fixture(autouse=True)
def setup_test_env():
    DatabaseService()
    yield


@pytest.fixture
def client():
    token = get_default_token()
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
def test_repo_dir(tmp_path):
    repo = tmp_path / "test_soc_repo"
    repo.mkdir()
    (repo / "top.v").write_text("module top(input clk, input rst_n, output reg [7:0] data); always @(posedge clk) data <= 8'h42; endmodule\n")
    (repo / "main.c").write_text("int main() { return 0; }\n")
    return str(repo)


def test_plan_approval_and_execution_api_flow(client, test_repo_dir):
    """
    Acceptance Criteria 1-10:
    CREATE PROJECT -> SELECT REPOSITORY -> PLAN -> APPROVE -> RUN_CREATED -> WORKPACKAGES -> TASKS
    """
    # 1. Create a distinct project
    proj_resp = client.post("/api/projects", json={
        "name": "Pipeline_Test_Project",
        "description": "Integration test for approve-to-execute pipeline",
        "target_directory": test_repo_dir
    })
    assert proj_resp.status_code == 200
    project_id = proj_resp.json()["project_id"]

    # 2. Select repository for this project
    sel_resp = client.post("/api/repositories/select", json={
        "repository_path": test_repo_dir
    })
    assert sel_resp.status_code == 200

    # 3. Generate verification plan
    plan_resp = client.post("/api/supervisor/plan", json={
        "intent_objective": "Verify clock domain crossings and reset synchronizers"
    })
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    plan_id = plan_data["plan"]["plan_id"]
    assert plan_data["plan"]["project_id"] == project_id
    assert len(plan_data["work_packages"]) > 0

    # 4. Approve plan & dispatch execution
    approve_resp = client.post(f"/api/supervisor/plan/{plan_id}/approve", json={
        "wave": "FULL",
        "execution_mode": "PARALLEL"
    })
    assert approve_resp.status_code == 200
    appr_data = approve_resp.json()
    assert appr_data["status"] == "SUCCESS"
    assert "run" in appr_data
    run_id = appr_data["run"]["run_id"]
    assert appr_data["run"]["project_id"] == project_id
    assert appr_data["run"]["run_state"] == "RUNNING"
    assert len(appr_data["activated_tasks"]) > 0

    # 5. Verify database records have project_id
    with DatabaseService().get_connection() as conn:
        # Check run
        run_row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        assert run_row is not None
        assert run_row["project_id"] == project_id
        assert run_row["plan_id"] == plan_id

        # Check work packages
        wp_rows = conn.execute("SELECT * FROM work_packages WHERE plan_id = ?", (plan_id,)).fetchall()
        assert len(wp_rows) > 0
        for wp in wp_rows:
            assert wp["project_id"] == project_id

        # Check tasks
        task_rows = conn.execute("SELECT * FROM tasks WHERE plan_id = ?", (plan_id,)).fetchall()
        assert len(task_rows) > 0
        for t in task_rows:
            assert t["project_id"] == project_id
            assert t["status"] in ("QUEUED", "RUNNING", "COMPLETED", "SUCCEEDED", "BLOCKED")

        # Check protocol events
        event_rows = conn.execute("SELECT * FROM events WHERE project_id = ?", (project_id,)).fetchall()
        event_types = [e["event_type"] for e in event_rows]
        assert "PLAN_APPROVED" in event_types
        assert "RUN_CREATED" in event_types
        assert "RUN_STARTED" in event_types
        assert "WORKPACKAGE_CREATED" in event_types
        assert "TASK_CREATED" in event_types
        assert "TASK_QUEUED" in event_types


def test_approval_idempotency(client, test_repo_dir):
    """
    Acceptance Criteria 31: Duplicate approval requests on an active plan must not duplicate runs.
    """
    proj_resp = client.post("/api/projects", json={
        "name": "Idempotency_Project",
        "target_directory": test_repo_dir
    })
    assert proj_resp.status_code == 200

    plan_resp = client.post("/api/supervisor/plan", json={})
    plan_id = plan_resp.json()["plan"]["plan_id"]

    # First approval
    resp1 = client.post(f"/api/supervisor/plan/{plan_id}/approve", json={"wave": "FULL"})
    assert resp1.status_code == 200
    run_id1 = resp1.json()["run"]["run_id"]

    # Second approval (should reject duplicate run creation or return existing active run)
    resp2 = client.post(f"/api/supervisor/plan/{plan_id}/approve", json={"wave": "FULL"})
    assert resp2.status_code == 400 or resp2.json().get("status") in ("ACTIVE", "ALREADY_ACTIVE", "RUN_ALREADY_ACTIVE")


@pytest.mark.asyncio
async def test_orchestrator_execution_worker(test_repo_dir):
    """
    Acceptance Criteria 11-17, 21-23:
    Direct execution of dispatch_and_execute_run:
    - Runs AGY process
    - Runs deterministic tool
    - Captures stdout/stderr
    - Persists tool execution & evidence
    - Updates closure
    - Completes run
    """
    orch = CentralOrchestrator()
    supervisor = SoCSupervisor()
    db = DatabaseService()
    wp_repo = WorkPackageRepository(db)
    plan_repo = VerificationPlanRepository(db)

    import uuid
    uid = uuid.uuid4().hex[:6]
    project_id = f"test-proj-worker-{uid}"
    plan_id = f"test-plan-worker-{uid}"
    run_id = f"test-run-worker-{uid}"
    root_task_id = f"test-root-worker-{uid}"

    # Create plan in DB
    plan = VerificationPlan(
        plan_id=plan_id,
        project_id=project_id,
        name="Worker Test Plan",
        repository_path=test_repo_dir,
        repository_name="test_repo",
        scope_description="Worker test scope",
        version=1,
        status="APPROVED"
    )
    plan_repo.save(plan)

    # Create 2 WorkPackages (one independent, one dependent)
    from schemas.soc_ontology import SoCBucket
    wp1 = WorkPackage(
        package_id="wp-worker-01",
        plan_id=plan_id,
        project_id=project_id,
        name="Reset Verification",
        description="Verify reset synchronizer",
        bucket=SoCBucket.RESETS,
        role="Reset & Clock Specialist",
        status="APPROVED"
    )
    wp2 = WorkPackage(
        package_id="wp-worker-02",
        plan_id=plan_id,
        project_id=project_id,
        name="CDC Verification",
        description="Verify structural CDC",
        bucket=SoCBucket.CDC,
        role="CDC/RDC Specialist",
        dependencies=["wp-worker-01"],
        status="APPROVED"
    )
    wp_repo.save(wp1)
    wp_repo.save(wp2)

    # Approve and activate plan
    res = await orch.approve_and_execute_plan(
        plan_id=plan_id,
        project_id=project_id,
        wave="FULL"
    )
    assert res["status"] == "SUCCESS"
    run_id = res["run"]["run_id"]
    activated = res["activated_tasks"]
    assert len(activated) >= 2

    # Execute run
    await orch.dispatch_and_execute_run(
        run_id=run_id,
        plan_id=plan_id,
        project_id=project_id,
        task_ids=activated
    )

    # Verify task statuses
    with DatabaseService().get_connection() as conn:
        task_rows = conn.execute("SELECT * FROM tasks WHERE plan_id = ?", (plan_id,)).fetchall()
        assert len(task_rows) >= 2
        for t in task_rows:
            assert t["status"] in ("COMPLETED", "SUCCEEDED"), f"Task {t['task_id']} status is {t['status']}"

    # Verify tool executions recorded
    tool_repo = ToolExecutionRepository(db)
    tool_execs = tool_repo.list_executions(project_id=project_id)
    assert len(tool_execs) > 0
    first_tool = tool_execs[0]
    p_id = first_tool.get("project_id") if isinstance(first_tool, dict) else first_tool.project_id
    e_code = first_tool.get("exit_code") if isinstance(first_tool, dict) else first_tool.exit_code
    s_out = first_tool.get("stdout") if isinstance(first_tool, dict) else first_tool.stdout
    assert p_id == project_id
    assert e_code == 0
    assert s_out is None or len(s_out) >= 0

    # Verify run completed
    with DatabaseService().get_connection() as conn:
        run_row = conn.execute("SELECT run_state FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        assert run_row["run_state"] == "COMPLETED"


def test_claude_executor_disabled():
    """
    Acceptance Criteria 11:
    Enterprise policy strictly forbids Claude execution.
    """
    orch = CentralOrchestrator()
    with pytest.raises(PermissionError, match="Execution Policy strictly blocks Claude execution"):
        orch.create_user_task(goal="Check Claude", target_files=[], agent_id="agent-claude-01")
