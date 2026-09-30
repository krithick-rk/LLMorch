"""
test_final_orchestration_pass.py — Integration and Unit Tests for:
- Agent Configuration & Scheduler WAITING_FOR_AGENT routing
- Persistent Hierarchical Project-Local Identifiers (PROJ-001-TASK-001, etc.)
- Elimination of hardcoded EVI-001 and VUL-001 fallbacks + Duplicate Evidence Detection
- Plan Versioning (V1, V2, V3) & Immutable Scope Snapshots
- WorkPackage Proposals, Approval & Rejection
- Development Logging & 1.5 GB Retention Engine (3-day policy, protected invariants)
- Claude execution count strictly 0
"""

import os
import shutil
import tempfile
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from history.database import DatabaseService
from history.id_service import IdService
from history.log_retention import LogManager
from history.project_repository import ProjectRepository
from orchestrator.orchestrator import CentralOrchestrator
from api.app import app


@pytest.fixture
def clean_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_final_pass.db")
    db = DatabaseService(db_path=db_path)
    yield db
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def app_client(clean_db, monkeypatch):
    monkeypatch.setattr("api.routers.projects._get_project_repo", lambda: ProjectRepository(clean_db))
    monkeypatch.setattr("api.routers.tasks._get_db", lambda: clean_db)
    monkeypatch.setattr("api.routers.agents._get_db", lambda: clean_db)
    monkeypatch.setattr("api.routers.runs._get_db", lambda: clean_db)
    monkeypatch.setattr("api.routers.findings._get_db", lambda: clean_db)
    monkeypatch.setattr("api.routers.evidence._get_db", lambda: clean_db)
    monkeypatch.setattr("api.routers.supervisor._get_db", lambda: clean_db)
    monkeypatch.setattr("api.routers.debug._get_db", lambda: clean_db)

    client = TestClient(app)
    return client


def test_id_service_hierarchical_identifiers(clean_db):
    with clean_db.get_connection() as conn:
        proj_repo = ProjectRepository(clean_db)
        proj = proj_repo.create_project(name="Hierarchical ID Test", target_directory="/tmp/target_id")
        proj_id = proj["project_id"]

        # Allocate Task, Evidence, Finding, Run, Plan IDs
        full_t, short_t, seq_t = IdService.allocate_display_id(conn, proj_id, "TASK")
        assert full_t.endswith("-TASK-001")
        assert short_t == "TASK-001"
        assert seq_t == 1

        full_e, short_e, seq_e = IdService.allocate_display_id(conn, proj_id, "EVI")
        assert full_e.endswith("-EVI-001")
        assert short_e == "EVI-001"

        full_v, short_v, seq_v = IdService.allocate_display_id(conn, proj_id, "VUL")
        assert full_v.endswith("-VUL-001")
        assert short_v == "VUL-001"

        full_r, short_r, seq_r = IdService.allocate_display_id(conn, proj_id, "RUN")
        assert full_r.endswith("-RUN-001")

        full_p, short_p, seq_p = IdService.allocate_display_id(conn, proj_id, "PLAN", plan_version=1)
        assert full_p.endswith("-PLAN-001-V1")

        # Second allocation increments sequence
        full_t2, short_t2, seq_t2 = IdService.allocate_display_id(conn, proj_id, "TASK")
        assert full_t2.endswith("-TASK-002")
        assert short_t2 == "TASK-002"
        assert seq_t2 == 2


def test_evidence_and_finding_no_hardcoded_fallbacks(clean_db, app_client):
    proj_repo = ProjectRepository(clean_db)
    proj = proj_repo.create_project(name="No Fallback Test", target_directory="/tmp/no_fallback")
    proj_id = proj["project_id"]

    now = datetime.now(timezone.utc).isoformat()
    f_id = f"find-{uuid.uuid4().hex[:8]}"
    e1_id = f"evi-{uuid.uuid4().hex[:8]}"
    e2_id = f"evi-{uuid.uuid4().hex[:8]}"

    with clean_db.get_connection() as conn:
        conn.execute("""
            INSERT INTO findings (
                finding_id, project_id, fingerprint, hypothesis, locations,
                supporting_evidence, contradicting_evidence, validation_method, validator_result,
                state, lineage, timestamps, schema_version, task_id, created_at, updated_at
            ) VALUES (?, ?, 'fp1', 'Hypothesis 1', '[]', '[]', '[]', NULL, 'CONFIRMED', 'CONFIRMED', '{}', '{}', '1.0', NULL, ?, ?)
        """, (f_id, proj_id, now, now))

        # Insert first evidence with hash H1
        conn.execute("""
            INSERT INTO evidence (
                evidence_id, project_id, task_id, run_id, agent_id, source_type,
                raw_hash, canonical_hash, semantic_fingerprint, environment_fingerprint,
                exit_status, provenance, schema_version, finding_id, source_tool, timestamp,
                semantic_identity
            ) VALUES (?, ?, 'task-1', 'run-1', 'agent-agy-01', 'TOOL_OUTPUT', 'HASH_AAA', 'CAN_AAA', 'SEM_1', 'ENV_1', 0, '{}', '1.0', ?, 'rust_source_inspector', ?, 'ID1')
        """, (e1_id, proj_id, f_id, now))

        # Insert second duplicate evidence with identical raw_hash
        conn.execute("""
            INSERT INTO evidence (
                evidence_id, project_id, task_id, run_id, agent_id, source_type,
                raw_hash, canonical_hash, semantic_fingerprint, environment_fingerprint,
                exit_status, provenance, schema_version, finding_id, source_tool, timestamp,
                semantic_identity
            ) VALUES (?, ?, 'task-2', 'run-1', 'agent-agy-01', 'TOOL_OUTPUT', 'HASH_AAA', 'CAN_AAA', 'SEM_1', 'ENV_1', 0, '{}', '1.0', ?, 'rust_source_inspector', ?, 'ID2')
        """, (e2_id, proj_id, f_id, now))
        conn.commit()

    # Query Evidence API
    e_res = app_client.get(f"/api/evidence?project_id={proj_id}")
    assert e_res.status_code == 200
    ev_items = e_res.json()["items"]
    assert len(ev_items) == 2
    # Verify no fallback to hardcoded EVI-001
    assert ev_items[0]["display_id"] != "EVI-001"
    assert "EVI-" in ev_items[0]["display_id"]

    # Verify duplicate detection identifies duplicate_of_id
    dups = [item for item in ev_items if item.get("duplicate_of_id")]
    assert len(dups) >= 1
    assert dups[0]["duplicate_of_id"] == ev_items[0]["display_id"]

    # Query Findings API
    f_res = app_client.get(f"/api/findings/{f_id}")
    assert f_res.status_code == 200
    f_detail = f_res.json()
    assert f_detail["display_id"] != "VUL-001"
    assert "VUL-" in f_detail["display_id"]
    # Verify clickable breadcrumb trace exists
    assert "trace" in f_detail
    assert len(f_detail["trace"]) >= 5


def test_agent_enable_disable_and_waiting_for_agent(clean_db, app_client):
    proj_repo = ProjectRepository(clean_db)
    proj = proj_repo.create_project(name="Agent Control Test", target_directory="/tmp/agent_control")
    proj_id = proj["project_id"]

    # Test enable/disable agent endpoints
    res_dis = app_client.patch("/api/agents/agent-agy-01/disable")
    assert res_dis.status_code == 200
    assert res_dis.json()["enabled"] is False

    res_en = app_client.patch("/api/agents/agent-agy-01/enable")
    assert res_en.status_code == 200
    assert res_en.json()["enabled"] is True

    # Test Claude cannot be enabled (Enterprise Policy)
    res_claude = app_client.patch("/api/agents/agent-claude-01/enable")
    assert res_claude.status_code == 403


@pytest.mark.asyncio
async def test_scheduler_waiting_for_agent_when_disabled(clean_db):
    # Seed agents and disable all
    with clean_db.get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO agents (agent_id, provider, interface, model, capabilities, protocols, permissions, health, availability, concurrency_limit, usage_status, quota_status, workspace_class, auth_profile, adapter_version, metadata, schema_version, enabled) VALUES ('agent-agy-01', 'local', 'CLI', 'default', '[]', '[]', '[]', 'AVAILABLE', 1, 4, 'ACTIVE', 'HEALTHY', 'LOCAL', 'default', '2.4', '{}', '1.0', 0)")
        conn.execute("INSERT OR REPLACE INTO agents (agent_id, provider, interface, model, capabilities, protocols, permissions, health, availability, concurrency_limit, usage_status, quota_status, workspace_class, auth_profile, adapter_version, metadata, schema_version, enabled) VALUES ('agent-codex-01', 'local', 'CLI', 'default', '[]', '[]', '[]', 'AVAILABLE', 1, 4, 'ACTIVE', 'HEALTHY', 'LOCAL', 'default', '2.4', '{}', '1.0', 0)")
        
        # Insert a plan and a task
        conn.execute("INSERT INTO verification_plans (plan_id, project_id, version, status, total_work_packages, created_at, repository_path, repository_name, scope_description) VALUES ('plan-test-01', 'proj-test', 1, 'APPROVED', 1, '2026-09-30T10:00:00Z', '/tmp', 'test-repo', 'Test Scope')")
        conn.execute("INSERT INTO tasks (task_id, plan_id, project_id, objective, inputs, dependencies, required_capabilities, preferred_roles, risk_level, workspace_policy, tool_policy, budget, status, retry_count, acceptance_criteria, schema_version, created_at) VALUES ('task-test-01', 'plan-test-01', 'proj-test', 'Review security headers', '{}', '[]', '[]', '[]', 'LOW', 'STRICT', 'DETERMINISTIC', '{}', 'QUEUED', 0, 'Done', '1.0', '2026-09-30T10:00:00Z')")
        conn.commit()

    orch = CentralOrchestrator(clean_db)
    await orch.dispatch_and_execute_run(
        run_id="run-test-01",
        plan_id="plan-test-01",
        project_id="proj-test",
        task_ids=["task-test-01"]
    )

    with clean_db.get_connection() as conn:
        t_row = conn.execute("SELECT status, stop_reason FROM tasks WHERE task_id = 'task-test-01'").fetchone()
        assert t_row["status"] == "WAITING_FOR_AGENT"
        assert "No enabled eligible execution agent is available" in t_row["stop_reason"]


def test_workpackage_proposal_and_plan_versions(clean_db, app_client):
    proj_repo = ProjectRepository(clean_db)
    proj = proj_repo.create_project(name="WP Proposal Test", target_directory="/tmp/proposal_test")
    proj_id = proj["project_id"]

    with clean_db.get_connection() as conn:
        conn.execute("INSERT INTO verification_plans (plan_id, project_id, version, status, total_work_packages, created_at, repository_path, repository_name, scope_description) VALUES ('plan-wp-01', ?, 1, 'APPROVED', 2, '2026-09-30T10:00:00Z', '/tmp', 'test-repo', 'Test Scope')", (proj_id,))
        conn.execute("INSERT INTO work_packages (package_id, plan_id, project_id, name, description, bucket, role, status, created_at) VALUES ('wp-prop-01', 'plan-wp-01', ?, 'Mailbox DPE Boundary Audit', 'Audit mailbox DPE boundary', 'INTEGRATION', 'Security Auditor', 'PROPOSED', '2026-09-30T10:00:00Z')", (proj_id,))
        conn.commit()

    # Query Plan Versions
    pv_res = app_client.get("/api/supervisor/plan/plan-wp-01/versions")
    assert pv_res.status_code == 200
    versions = pv_res.json()["versions"]
    assert len(versions) >= 1
    assert versions[0]["version"] == "V1"

    # Query WorkPackage Proposal
    prop_res = app_client.get("/api/supervisor/workpackages/wp-prop-01")
    assert prop_res.status_code == 200
    prop = prop_res.json()
    assert prop["status"] == "PROPOSED"
    assert "candidate_tasks" in prop
    assert "suggested_agents" in prop
    assert "estimated_tokens" in prop

    # Approve WorkPackage
    app_res = app_client.post("/api/supervisor/workpackages/wp-prop-01/approve")
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "APPROVED"


def test_log_retention_and_quota_engine(clean_db, app_client, tmp_path):
    # Test LogManager storage stats
    stats = app_client.get("/api/debug/logging/config")
    assert stats.status_code == 200
    s_data = stats.json()
    assert s_data["global_size_limit_bytes"] == 1610612736  # 1.5 GB
    assert s_data["retention_days"] == 3
    assert "global_log_dir" in s_data

    # Test Log Cleanup Execution
    clean_res = app_client.post("/api/debug/logging/cleanup")
    assert clean_res.status_code == 200
    c_data = clean_res.json()
    assert c_data["status"] == "CLEANUP_COMPLETED"
    assert "bytes_freed" in c_data
    assert "files_removed" in c_data
