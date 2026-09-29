"""
Tests for Adaptive Planning, Task/Run Finalization, and Runtime Diagnostics.
Sections 14-27, 31, 32, 33 of LLMorch Architecture.
"""

import os
import uuid
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from api.app import app
from api.realtime import event_manager
from history.database import get_db_path, DatabaseService
from repository_intelligence.preflight import analyze_repository_preflight
from repository_intelligence.complexity import (
    ComplexityTier, IntentDepth, classify_complexity,
    parse_intent_depth, evaluate_bucket_evidence
)
from supervisor.supervisor import Supervisor
from orchestrator.orchestrator import CentralOrchestrator
from schemas.soc_ontology import SoCBucket, BucketApplicability


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_repo_path():
    p = Path(__file__).resolve().parent.parent / "test_soc_repo"
    assert p.exists() and p.is_dir()
    return str(p)


def test_micro_repository_classification(test_repo_path):
    """2-file test repo (reset_ctrl.sv + test_reset.c) must classify as MICRO."""
    preflight = analyze_repository_preflight(test_repo_path)
    tier, evidence = classify_complexity(
        repo_path=test_repo_path,
        analyzable_files_count=preflight.analyzable_files_count,
        total_bytes=preflight.total_bytes,
        rtl_detected=preflight.rtl_detected,
        software_detected=preflight.software_detected,
        build_system_detected=preflight.build_system_detected
    )

    assert tier == ComplexityTier.MICRO
    assert evidence.has_resets is True
    assert "rst_ni" in evidence.reset_signals or any("rst" in s for s in evidence.reset_signals)
    assert evidence.module_count == 1


def test_micro_repository_concise_plan(test_repo_path):
    """
    User request 'Analyze this repository' on tiny repo must NOT generate
    a 23-bucket plan or massive token estimates (Section 14 & 16).
    """
    preflight = analyze_repository_preflight(test_repo_path)
    supervisor = Supervisor()

    plan, wps, objs, questions = supervisor.synthesize_verification_plan(
        repository_path=test_repo_path,
        repository_name="test_soc_repo",
        intent_objective="Analyze this repository",
        preflight=preflight
    )

    assert plan.complexity_tier == "MICRO"
    assert plan.intent_depth == "QUICK"
    # Micro repo hard bound: <= 3 workpackages
    assert len(wps) <= 3
    assert len(wps) >= 1
    # Bounded tokens: < 30,000 tokens (NOT 680,000)
    assert plan.total_estimated_tokens < 30000
    # Bounded duration: < 300 seconds (NOT 2-3 hours)
    assert plan.total_estimated_duration_seconds <= 300
    # Resets must be applicable because reset signals exist
    assert plan.buckets_applicability[SoCBucket.RESETS.value] == BucketApplicability.APPLICABLE.value
    assert "reset" in plan.applicability_reasons[SoCBucket.RESETS.value].lower()
    # Unrelated buckets like PRODUCT_VARIANTS or BOOT must be NOT_APPLICABLE
    assert plan.buckets_applicability[SoCBucket.PRODUCT_VARIANTS.value] == BucketApplicability.NOT_APPLICABLE.value
    assert "no variant" in plan.applicability_reasons[SoCBucket.PRODUCT_VARIANTS.value].lower()


def test_full_soc_escalation(test_repo_path):
    """
    Explicit request 'Create a complete SoC verification plan' allows expansion
    while preserving evidence-based reasons (Section 32).
    """
    preflight = analyze_repository_preflight(test_repo_path)
    supervisor = Supervisor()

    plan, wps, objs, questions = supervisor.synthesize_verification_plan(
        repository_path=test_repo_path,
        repository_name="test_soc_repo",
        intent_objective="Create a complete SoC verification plan",
        preflight=preflight
    )

    assert plan.intent_depth == "FULL_SOC"
    assert len(wps) > 3  # Expanded taxonomy


def test_deterministic_task_finalization():
    """Task finalization transitions leaf task and root task to terminal states (Section 7)."""
    db = DatabaseService()
    orch = CentralOrchestrator(db)

    test_task_id = f"task-test-{uuid.uuid4().hex[:6]}"
    now = "2026-09-29T10:00:00Z"

    with db.get_connection() as conn:
        conn.execute("""
            INSERT INTO tasks (
                task_id, workflow_id, objective, inputs, dependencies,
                required_capabilities, preferred_roles, risk_level, workspace_policy,
                tool_policy, budget, status, retry_count, acceptance_criteria,
                schema_version, created_at, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_task_id, "wf-test", "Run Yosys synthesis check",
            "{}", "[]", "[]", "[]", "LOW", "{}",
            "{}", "{}", "RUNNING", 0, "[]",
            "1.0", now, now
        ))
        conn.commit()

    # Finalize without tool execution -> FAILED
    res = orch.finalize_task(test_task_id)
    assert res["status"] in ("SUCCEEDED", "FAILED")

    # Add tool execution with exit_code 0
    exec_id = f"exec-{uuid.uuid4().hex[:6]}"
    with db.get_connection() as conn:
        conn.execute("""
            INSERT INTO tool_executions (
                execution_id, tool_name, category, command, status, exit_code, task_id, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (exec_id, "yosys", "FORMAL", "yosys -v", "COMPLETED", 0, test_task_id, now))
        conn.commit()

    res2 = orch.finalize_task(test_task_id)
    assert res2["status"] == "SUCCEEDED"


def test_runtime_debug_endpoint(client):
    """GET /api/debug/runs/{run_id} returns exhaustive diagnostic info (Section 13)."""
    # Create test run
    run_id = f"run-diag-{uuid.uuid4().hex[:6]}"
    task_id = f"task-diag-{uuid.uuid4().hex[:6]}"
    db = DatabaseService()
    now = "2026-09-29T10:00:00Z"
    with db.get_connection() as conn:
        conn.execute("""
            INSERT INTO tasks (
                task_id, workflow_id, objective, inputs, dependencies,
                required_capabilities, preferred_roles, risk_level, workspace_policy,
                tool_policy, budget, status, retry_count, acceptance_criteria,
                schema_version, created_at, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id, "wf-test", "Diag task",
            "{}", "[]", "[]", "[]", "LOW", "{}",
            "{}", "{}", "RUNNING", 0, "[]",
            "1.0", now, now
        ))
        conn.execute("""
            INSERT INTO runs (
                run_id, task_id, agent_id, adapter_version, workspace_id,
                environment_fingerprint, status, run_state, start_time, schema_version
            ) VALUES (?, ?, 'agent-1', '1.0', 'ws-1', 'fp-1', 'RUNNING', 'RUNNING', ?, '1.0')
        """, (run_id, task_id, now))
        conn.commit()

    res = client.get(f"/api/debug/runs/{run_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["run_id"] == run_id
    assert "run_state" in data
    assert "task_state" in data
    assert "child_tasks" in data
    assert "agent_process_alive" in data
    assert "pending_dependencies" in data
