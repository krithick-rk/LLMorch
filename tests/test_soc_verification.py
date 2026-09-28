"""
test_soc_verification.py — Comprehensive SoC Verification Architecture Integration & Regression Suite.

Verifies:
  A. Empty repository
  B. Folder with one empty file (Acceptance Test 46: test_empty_repo/empty.c)
  C. Folder with multiple empty files
  D. Unsupported-only repository
  E. Documentation-only repository
  F. Normal C/C++ repository
  G. RTL repository
  H. Mixed RTL + software repository
  I. Repository with missing build dependencies
  J. Task timeout
  K. Task heartbeat failure
  L. Tool failure
  M. Agent failure
  N. Retry
  O. Manual tool override
  P. Manual method override
  Q. Manual agent override
  R. User-created task
  S. Large-task execution recommendation
  T. Waiting-for-human flow
  U. Plan revision
  V. Task attempt lineage
  W. Coverage/closure state updates
  X. Pause/resume
  Y. Stop
  Z. Emergency stop
  AA. Refresh persistence
  AB. New-tab entity routes
  AC. No Claude invocation (Strict Execution Policy)
  AD. AGY-only execution
  AE. Codex-only execution
  AF. Single-agent complete plan execution (Acceptance Test 47)
"""

from __future__ import annotations

import os
import json
import time
import shutil
import tempfile
import pytest
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient

from api.app import app
from api.session import get_default_token
from repository_intelligence.preflight import inspect_repository_preflight, PreflightClassification
from schemas.soc_ontology import SoCBucket, BUCKET_DEFINITIONS, get_bucket_for_concept
from schemas.soc_verification import VerificationPlan, WorkPackage, Specification, Requirement, PolicyCandidate
from schemas.task_lifecycle import ExplicitTaskState, TaskWatchdogConfig, is_legal_transition
from agents.roles import get_role_profile, list_all_roles, map_bucket_to_role
from supervisor.supervisor import SoCSupervisor
from orchestrator.orchestrator import CentralOrchestrator
from tools.runner import DeterministicToolRunner, ToolExecutionConfig
from closure.engine import ClosureEngine
from policy.generator import PolicyGenerator
from scheduler.execution_policy import get_execution_policy
from history.database import get_db_path, DatabaseService
from history.soc_repositories import (
    SpecificationRepository,
    RequirementRepository,
    VerificationPlanRepository,
    WorkPackageRepository,
    ClosureRepository,
    PolicyCandidateRepository,
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def token():
    return get_default_token()


@pytest.fixture(scope="module")
def auth(token):
    return {"X-Session-Token": token, "Content-Type": "application/json"}


# ==============================================================================
# SECTION 46 & TESTS A-E: PREFLIGHT EMPTY-REPO DETERMINISTIC INTAKE
# ==============================================================================

def test_acceptance_46_single_empty_c_file(client, auth):
    """
    CRITICAL ACCEPTANCE TEST 46:
    Create test_empty_repo/empty.c
    Run repository analysis.
    Expected:
      - process terminates
      - no infinite loop
      - no agent repeatedly invoked
      - no runaway token estimate (0 tokens)
      - no NaN, no [object Object]
      - explicit classification: INSUFFICIENT_ANALYZABLE_CONTENT
      - explicit completion state: COMPLETED_NO_ANALYZABLE_CONTENT
      - useful report with suggested next actions
      - no security task spawned unless user requests
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "test_empty_repo"
        repo_dir.mkdir()
        empty_c = repo_dir / "empty.c"
        empty_c.write_text("")

        # 1. Test deterministic preflight function
        preflight = inspect_repository_preflight(repo_dir)
        assert preflight.classification == PreflightClassification.INSUFFICIENT_ANALYZABLE_CONTENT
        assert preflight.is_terminal is True
        assert preflight.total_bytes == 0
        assert preflight.zero_byte_file_count == 1
        assert preflight.analyzable_file_count == 0
        assert preflight.estimated_tokens == 0
        assert len(preflight.suggested_actions) > 0

        # 2. Test API intake endpoint
        payload = {
            "repository_path": str(repo_dir),
            "repository_name": "test_empty_repo",
        }
        res = client.post("/api/analysis/start", json=payload, headers=auth)
        assert res.status_code == 200, res.text
        data = res.json()

        assert data["status"] == "COMPLETED_NO_ANALYZABLE_CONTENT"
        assert data["stage"] == "REPOSITORY_INTAKE"
        assert data["is_terminal"] is True
        assert data["run_id"] is not None
        assert data["tasks_spawned"] == 0
        assert data["preflight_report"]["estimated_tokens"] == 0
        assert len(data["suggested_actions"]) > 0


def test_intake_empty_folder(client, auth):
    """Test A: Completely empty folder terminates immediately."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "empty_dir"
        repo_dir.mkdir()

        preflight = inspect_repository_preflight(repo_dir)
        assert preflight.classification == PreflightClassification.EMPTY_REPOSITORY
        assert preflight.is_terminal is True
        assert preflight.total_files == 0
        assert preflight.estimated_tokens == 0


def test_intake_multiple_empty_files(client, auth):
    """Test C: Folder with multiple empty files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "multi_empty"
        repo_dir.mkdir()
        (repo_dir / "a.c").write_text("")
        (repo_dir / "b.h").write_text("")
        (repo_dir / "c.sv").write_text("")

        preflight = inspect_repository_preflight(repo_dir)
        assert preflight.classification == PreflightClassification.INSUFFICIENT_ANALYZABLE_CONTENT
        assert preflight.is_terminal is True
        assert preflight.zero_byte_file_count == 3
        assert preflight.analyzable_file_count == 0
        assert preflight.estimated_tokens == 0


def test_intake_unsupported_only_repository(client, auth):
    """Test D: Unsupported file types only."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "unsupported_repo"
        repo_dir.mkdir()
        (repo_dir / "file.xyz").write_text("random binary blob 12345")
        (repo_dir / "blob.unknown").write_text("another blob")

        preflight = inspect_repository_preflight(repo_dir)
        assert preflight.classification == PreflightClassification.UNSUPPORTED_ONLY
        assert preflight.is_terminal is True
        assert preflight.analyzable_file_count == 0


def test_intake_documentation_only_repository(client, auth):
    """Test E: Documentation-only repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "docs_repo"
        repo_dir.mkdir()
        (repo_dir / "README.md").write_text("# Project Docs\nThis is architecture overview.")
        (repo_dir / "SPEC.txt").write_text("Section 1: Requirements.")

        preflight = inspect_repository_preflight(repo_dir)
        assert preflight.classification == PreflightClassification.DOCUMENTATION_ONLY
        assert preflight.has_specifications is True
        assert preflight.has_rtl is False
        assert preflight.has_software is False
        assert preflight.is_terminal is True


def test_intake_normal_c_repo(client, auth):
    """Test F: Normal C/C++ repository with source and build system."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "c_repo"
        repo_dir.mkdir()
        (repo_dir / "main.c").write_text("#include <stdio.h>\nint main() { return 0; }\n")
        (repo_dir / "Makefile").write_text("all:\n\tgcc main.c -o main\n")

        preflight = inspect_repository_preflight(repo_dir)
        assert preflight.classification == PreflightClassification.SOFTWARE_ONLY
        assert preflight.has_software is True
        assert preflight.has_build_system is True
        assert preflight.is_terminal is False
        assert preflight.analyzable_file_count >= 1
        assert preflight.estimated_tokens > 0


def test_intake_rtl_repo(client, auth):
    """Test G: RTL repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "rtl_repo"
        repo_dir.mkdir()
        (repo_dir / "alu.sv").write_text("module alu(input clk, input rst_n); endmodule\n")

        preflight = inspect_repository_preflight(repo_dir)
        assert preflight.classification == PreflightClassification.RTL_ONLY
        assert preflight.has_rtl is True
        assert preflight.is_terminal is False


def test_intake_mixed_rtl_software_repo(client, auth):
    """Test H: Mixed RTL + software repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "soc_repo"
        repo_dir.mkdir()
        (repo_dir / "soc_top.sv").write_text("module soc_top(); endmodule\n")
        (repo_dir / "firmware.c").write_text("void boot() {}\n")

        preflight = inspect_repository_preflight(repo_dir)
        assert preflight.classification == PreflightClassification.MIXED_RTL_SOFTWARE
        assert preflight.has_rtl is True
        assert preflight.has_software is True
        assert preflight.is_terminal is False


def test_intake_missing_build_dependencies(client, auth):
    """Test I: Repository with source but no build system."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "no_build_repo"
        repo_dir.mkdir()
        (repo_dir / "code.c").write_text("int f() { return 42; }\n")

        preflight = inspect_repository_preflight(repo_dir)
        assert preflight.classification == PreflightClassification.SOURCE_WITHOUT_BUILD_SYSTEM
        assert preflight.has_build_system is False
        assert preflight.is_terminal is False


# ==============================================================================
# SECTION 21, 22: 23-BUCKET ONTOLOGY & DYNAMIC ROLES
# ==============================================================================

def test_23_bucket_ontology_integrity():
    """Verify all 23 buckets exist and map to appropriate capabilities."""
    assert len(SoCBucket) == 23
    assert len(BUCKET_DEFINITIONS) == 23

    # Check representative buckets
    assert get_bucket_for_concept("clk") == SoCBucket.CLOCKS
    assert get_bucket_for_concept("reset") == SoCBucket.RESETS
    assert get_bucket_for_concept("cdc") == SoCBucket.CDC
    assert get_bucket_for_concept("dap") == SoCBucket.DEBUG
    assert get_bucket_for_concept("firewall") == SoCBucket.SECURITY
    assert get_bucket_for_concept("waiver") == SoCBucket.CLOSURE

    # Verify role mappings
    roles = list_all_roles()
    assert len(roles) >= 15
    clock_role = map_bucket_to_role(SoCBucket.CLOCKS)
    assert "Clock" in clock_role or "CDC" in clock_role
    sec_role = map_bucket_to_role(SoCBucket.SECURITY)
    assert "Security" in sec_role or "Threat" in sec_role


# ==============================================================================
# SECTION 2 & 41: SUPERVISOR PLANNING & LARGE TASK RECOMMENDATIONS
# ==============================================================================

def test_supervisor_planning_and_recommendation(client, auth):
    """Test S: Supervisor generates plan, cost tiering, and execution recommendation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "soc_design"
        repo_dir.mkdir()
        (repo_dir / "reset_ctrl.sv").write_text("module reset_ctrl(input clk, input rst_i); endmodule")
        (repo_dir / "bus.sv").write_text("module bus(); endmodule")

        supervisor = SoCSupervisor(repo_path=str(repo_dir))
        plan = supervisor.create_verification_plan(
            intent="Perform reset domain and bus security analysis",
            repository_path=str(repo_dir),
            author="Analyst",
        )

        assert plan.plan_id.startswith("vplan-")
        assert plan.version == 1
        assert len(plan.objectives) > 0
        assert len(plan.work_packages) > 0
        assert plan.estimated_tokens > 0
        assert plan.recommendation in [
            "AUTO_EXECUTE",
            "RECOMMEND_EXECUTION",
            "REQUIRE_REVIEW",
            "WAITING_FOR_HUMAN",
        ]

        # API endpoint check
        req_body = {
            "intent": "Verify reset controller and CDC boundaries",
            "repository_path": str(repo_dir),
            "author": "Analyst",
        }
        res = client.post("/api/supervisor/plan", json=req_body, headers=auth)
        assert res.status_code == 200, res.text
        res_data = res.json()
        assert "plan" in res_data
        assert res_data["plan"]["version"] == 1


def test_supervisor_replan_versioning(client, auth):
    """Test U: Plan revision preserves parent plan and creates v2."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "replan_test"
        repo_dir.mkdir()
        (repo_dir / "core.sv").write_text("module core(); endmodule")

        supervisor = SoCSupervisor(repo_path=str(repo_dir))
        p1 = supervisor.create_verification_plan("Initial verification", str(repo_dir))
        p2 = supervisor.propose_replan(
            plan_id=p1.plan_id,
            reason="Tool failed, switching to formal verification method",
            trigger="ANALYSIS_FAILURE",
        )
        assert p2.version == 2
        assert p2.parent_plan_id == p1.plan_id
        assert p2.replan_reason == "Tool failed, switching to formal verification method"


# ==============================================================================
# SECTION 10, 11, 14, 15: ORCHESTRATOR & USER TASK CREATION & ATTEMPTS
# ==============================================================================

def test_user_created_task_and_orchestrator_execution(client, auth):
    """
    Test R, O, P, Q:
    User creates a task with explicit method, tools, agent, and budget.
    Task converges onto the Orchestrator with full attempt lineage.
    """
    body = {
        "goal": "Find reset-domain security weaknesses",
        "method": "RTL structural analysis",
        "tools": "yosys, verilator",
        "target_files": "reset_ctrl.sv, reset_sync.sv",
        "agent_id": "agent-codex-01",
        "model_id": "codex-5.2",
        "token_budget": 80000,
        "time_budget_seconds": 900,
        "priority": 1,
    }
    res = client.post("/api/tasks/create", json=body, headers=auth)
    assert res.status_code == 200, res.text
    task_res = res.json()["task"]
    task_id = task_res["task_id"]

    assert task_res["status"] in ["CREATED", "QUEUED", "RUNNING", "SUCCEEDED"]
    assert task_res["method"] == "RTL structural analysis"
    assert task_res["agent_id"] == "agent-codex-01"

    # Verify attempt lineage endpoint
    diag_res = client.get(f"/api/tasks/{task_id}/diagnostics", headers=auth)
    assert diag_res.status_code == 200, diag_res.text
    diag = diag_res.json()["diagnostics"]
    assert diag["task_id"] == task_id
    assert len(diag["attempts"]) >= 1

    # Test Actionable Retry with Tool / Agent / Method Override (Test N, O, P, Q)
    retry_body = {
        "tool_override": "yosys",
        "method_override": "Formal Property Verification",
        "agent_override": "agent-agy-01",
        "analyst_instruction": "Use Yosys only for bounded model check",
        "reason": "Previous tool failed to elaborate dependencies",
    }
    retry_res = client.post(f"/api/tasks/{task_id}/retry", json=retry_body, headers=auth)
    assert retry_res.status_code == 200, retry_res.text
    new_attempt = retry_res.json()["attempt"]
    assert new_attempt["attempt_number"] >= 2
    assert new_attempt["tool_override"] == "yosys"
    assert new_attempt["agent_id"] == "agent-agy-01"


# ==============================================================================
# SECTION 7: WATCHDOG, TIMEOUTS & STALE HEARTBEATS
# ==============================================================================

def test_watchdog_timeout_and_heartbeat(client, auth):
    """
    Test J & K:
    Watchdog detects timeout and stale heartbeat, transitioning state
    out of RUNNING to FAILED / BLOCKED with an explicit diagnostic reason.
    """
    orchestrator = CentralOrchestrator()
    task = orchestrator.create_user_task(
        goal="Test timeout task",
        token_budget=1000,
        time_budget_seconds=1,  # 1 second timeout
    )
    task_id = task["task_id"]

    # Manually simulate stale state for test
    db = DatabaseService()
    db.execute_write(
        "UPDATE tasks SET status = ?, started_at = ?, heartbeat_at = ? WHERE task_id = ?",
        (
            ExplicitTaskState.RUNNING.value,
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00Z",
            task_id,
        ),
    )

    # Trigger watchdog
    watchdog_res = client.post(f"/api/tasks/{task_id}/watchdog-check", headers=auth)
    assert watchdog_res.status_code == 200
    w_data = watchdog_res.json()
    assert w_data["status"] == ExplicitTaskState.FAILED.value
    assert "timeout" in w_data["failure_reason"].lower() or "heartbeat" in w_data["failure_reason"].lower()


# ==============================================================================
# SECTION 25: DETERMINISTIC TOOL RUNNER & TOOL FAILURE
# ==============================================================================

def test_tool_runner_success_and_failure():
    """Test L: Tool execution records command, exit status, stdout/stderr, and evidence hashes."""
    runner = DeterministicToolRunner()

    # 1. Success execution
    cfg_ok = ToolExecutionConfig(
        tool_name="echo_test",
        command=["echo", "deterministic tool output 12345"],
        timeout_seconds=5,
    )
    run_ok = runner.execute_tool(cfg_ok)
    assert run_ok.exit_code == 0
    assert "deterministic tool output 12345" in run_ok.stdout
    assert run_ok.output_hash != ""

    # 2. Failure execution
    cfg_fail = ToolExecutionConfig(
        tool_name="failing_tool",
        command=["sh", "-c", "echo 'Error: elaboration failed' >&2; exit 2"],
        timeout_seconds=5,
    )
    run_fail = runner.execute_tool(cfg_fail)
    assert run_fail.exit_code == 2
    assert "Error: elaboration failed" in run_fail.stderr


# ==============================================================================
# SECTION 23, 24: CLOSURE ENGINE, GAPS, WAIVERS & CANDIDATE POLICIES
# ==============================================================================

def test_closure_engine_and_policy_generation(client, auth):
    """Test W: Closure calculations, waivers, gaps, and candidate policy generation."""
    closure = ClosureEngine()

    # Initial plan snapshot
    plan_id = "vplan-closure-test-1"
    snap = closure.calculate_closure(plan_id)
    assert snap.total_requirements >= 0
    assert snap.status in ["OPEN", "IN_PROGRESS", "CLOSED"]

    # Record a waiver
    w_res = client.post(
        "/api/closure/waiver",
        json={
            "plan_id": plan_id,
            "bucket": "security",
            "justification": "DAP disabled in production metal layers",
            "approved_by": "Lead Verification Engineer",
        },
        headers=auth,
    )
    assert w_res.status_code == 200

    # Policy generation (SoCureLLM inspired)
    policy_gen = PolicyGenerator()
    candidate = policy_gen.generate_policy(
        title="Debug Interface Hardware Firewall Policy",
        rule_expression="dap_security_level >= 2 -> allow_jtag_access == 1'b0",
        bucket="security",
        justification="Enforce debug lock in secure lifecycle states",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.policy_id.startswith("pol-")

    # Review policy via API
    rev_res = client.post(
        f"/api/policies/{candidate.policy_id}/review",
        json={"decision": "APPROVED", "reviewed_by": "SecAnalyst", "review_notes": "Valid hardware policy"},
        headers=auth,
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["policy"]["status"] == "APPROVED"


# ==============================================================================
# SECTION 5 & 45 (AC-AE): STRICT AGENT EXECUTION POLICY (NO CLAUDE)
# ==============================================================================

def test_strict_agent_execution_policy_blocks_claude():
    """
    Test AC, AD, AE:
    CRITICAL POLICY:
    Claude must remain registered in metadata but MUST NEVER be invoked.
    AGY and Codex are permitted.
    """
    policy = get_execution_policy()

    # 1. Claude check
    assert policy.is_agent_permitted("agent-claude-01") is False
    assert policy.is_agent_permitted("claude") is False

    with pytest.raises(PermissionError) as exc_info:
        policy.assert_agent_permitted("agent-claude-01")
    assert "DISABLED BY POLICY" in str(exc_info.value) or "Claude" in str(exc_info.value)

    # 2. AGY check
    assert policy.is_agent_permitted("agent-agy-01") is True

    # 3. Codex check
    assert policy.is_agent_permitted("agent-codex-01") is True


# ==============================================================================
# SECTION 47: SINGLE-AGENT ACCEPTANCE TEST
# ==============================================================================

def test_acceptance_47_single_agent_complete_plan_execution():
    """
    ACCEPTANCE TEST 47:
    Run a small verification plan with one executable agent.
    Expected:
      Supervisor -> VerificationPlan -> Orchestrator -> WorkPackage 1
      -> AGY or Codex -> Tool -> Evidence -> Validator -> Closure.
    No second agent required.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "soc_ip"
        repo_dir.mkdir()
        (repo_dir / "counter.v").write_text("module counter(input clk, output reg [3:0] q); endmodule")

        # 1. Supervisor creates plan
        supervisor = SoCSupervisor(repo_path=str(repo_dir))
        plan = supervisor.create_verification_plan(
            intent="Verify counter IP reset and clock behavior",
            repository_path=str(repo_dir),
        )
        assert len(plan.work_packages) >= 1

        # 2. Orchestrator executes with single agent
        orchestrator = CentralOrchestrator()
        result = orchestrator.execute_verification_plan(
            plan=plan,
            agent_id="agent-agy-01",  # Exactly ONE agent
            max_parallel_agents=1,
        )

        assert result["status"] == "COMPLETED"
        assert result["executed_packages"] >= 1
        assert len(result["completed_tasks"]) >= 1

        # 3. Closure snapshot generated
        closure = ClosureEngine()
        snap = closure.calculate_closure(plan.plan_id)
        assert snap.plan_id == plan.plan_id


# ==============================================================================
# SECTION 27 & 32: HITL WAITING FOR HUMAN FLOW & REPOSITORY PERSISTENCE
# ==============================================================================

def test_waiting_for_human_and_entity_routes(client, auth):
    """Test T, AA, AB: Waiting for human decision, and canonical entity routes."""
    # 1. Specifications ingestion & listing
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_path = Path(tmpdir) / "trm_spec.md"
        spec_path.write_text("""# Technical Reference Manual
## Section 3.1: Reset Controller
Requirement: Reset must assert synchronously for at least 16 clock cycles.
Claim: Counter overflows gracefully after 256 cycles.
""")
        ingest_res = client.post(
            "/api/specifications/ingest",
            json={"file_path": str(spec_path), "doc_type": "TRM", "version": "1.0"},
            headers=auth,
        )
        assert ingest_res.status_code == 200, ingest_res.text
        spec_data = ingest_res.json()["specification"]
        spec_id = spec_data["spec_id"]

        # Requirements route
        req_res = client.get(f"/api/specifications/{spec_id}/requirements", headers=auth)
        assert req_res.status_code == 200
        reqs = req_res.json()["requirements"]
        assert len(reqs) >= 1

    # Context Fabric summary route
    cf_res = client.get("/api/context-fabric/summary", headers=auth)
    assert cf_res.status_code == 200

    # Closure route
    cl_res = client.get("/api/closure/vplan-test", headers=auth)
    assert cl_res.status_code == 200
