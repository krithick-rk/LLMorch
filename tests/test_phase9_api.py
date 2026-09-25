"""
LLMorch Phase 9 — Backend API tests.

Tests the FastAPI endpoints using the HTTPX TestClient.
All tests use an isolated in-memory DB via LLMORCH_DB_PATH env override.
"""

import os
import json
import uuid
import pytest
from datetime import datetime, timezone

# Use an isolated temp DB for all Phase 9 API tests
_TEST_DB = f"/tmp/llmorch_phase9_test_{uuid.uuid4().hex[:8]}.db"
os.environ["LLMORCH_DB_PATH"] = _TEST_DB

from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app, raise_server_exceptions=True)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _seed_task(db, task_id=None, status="RUNNING"):
    from history.database import DatabaseService
    tid = task_id or f"task-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO tasks (task_id, workflow_id, parent_task_id, objective, inputs, "
            "dependencies, required_capabilities, preferred_roles, risk_level, workspace_policy, "
            "tool_policy, budget, status, assigned_agent_id, retry_count, acceptance_criteria, "
            "result_ref, schema_version, created_at, started_at, completed_at) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tid, "wf-test", None, "Test objective", "[]", "[]", "[]", "[]", "LOW",
             "{}", "{}", "{}", status, "agent-agy-01", 0, "[]", None, "1.0", now, now, None)
        )
    return tid


def _seed_agent(db, agent_id=None, provider="agy"):
    from history.database import DatabaseService
    aid = agent_id or f"agent-{provider}-01"
    with db.get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO agents (agent_id, provider, interface, model, capabilities, "
            "protocols, permissions, health, availability, concurrency_limit, usage_status, "
            "quota_status, workspace_class, auth_profile, adapter_version, metadata, schema_version) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, provider, "CLI", "default", '["security_review"]', "[]", "{}", "AVAILABLE",
             1, 1, "ACTIVE", "OK", "standard", "{}", "1.0", "{}", "1.0")
        )
    return aid


def _seed_finding(db, finding_id=None, state="OPEN"):
    from history.database import DatabaseService
    fid = finding_id or f"finding-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    fp = uuid.uuid4().hex
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO findings (finding_id, fingerprint, hypothesis, locations, "
            "supporting_evidence, contradicting_evidence, validation_method, validator_result, "
            "state, lineage, timestamps, schema_version, task_id, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (fid, fp, "Test hypothesis", "[]", "[]", "[]", None, None,
             state, "{}", "{}", "1.0", None, now, now)
        )
    return fid


def _seed_evidence(db, evidence_id=None, finding_id=None):
    from history.database import DatabaseService
    eid = evidence_id or f"ev-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO evidence (evidence_id, task_id, run_id, agent_id, source_type, "
            "raw_hash, canonical_hash, semantic_fingerprint, environment_fingerprint, "
            "exit_status, provenance, schema_version, finding_id, source_tool, timestamp, "
            "semantic_identity) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, "task-t1", "run-r1", "agent-agy-01", "TOOL_OUTPUT",
             "abc123", "def456", "semfp", "envfp", 0, "{}", "1.0",
             finding_id, "verilator", now, "sem-id-1")
        )
    return eid


def get_test_db():
    from history.database import get_db_path, DatabaseService
    return DatabaseService(get_db_path())


# ─── Health ───────────────────────────────────────────────────────────────────

def test_health_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "version" in data
    assert data["version"] == "9.0.0"


# ─── Session ──────────────────────────────────────────────────────────────────

def test_get_session():
    resp = client.get("/api/session")
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["role"] == "analyst"


def test_create_session():
    resp = client.post("/api/session")
    assert resp.status_code == 200
    data = resp.json()
    assert "session_token" in data
    assert len(data["session_token"]) > 10


# ─── Tasks ────────────────────────────────────────────────────────────────────

def test_list_tasks_empty():
    resp = client.get("/api/tasks?limit=5&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_list_tasks_pagination():
    db = get_test_db()
    for _ in range(5):
        _seed_task(db)

    r1 = client.get("/api/tasks?limit=3&offset=0").json()
    r2 = client.get("/api/tasks?limit=3&offset=3").json()
    assert r1["total"] >= 5
    assert len(r1["items"]) == 3
    # Ensure no overlap
    ids1 = {t["task_id"] for t in r1["items"]}
    ids2 = {t["task_id"] for t in r2["items"]}
    assert ids1.isdisjoint(ids2)


def test_list_tasks_status_filter():
    db = get_test_db()
    _seed_task(db, status="COMPLETED")
    resp = client.get("/api/tasks?status=COMPLETED")
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["status"] == "COMPLETED"


def test_get_task_detail():
    db = get_test_db()
    tid = _seed_task(db)
    resp = client.get(f"/api/tasks/{tid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == tid
    assert "runs" in data
    assert isinstance(data["runs"], list)


def test_get_task_not_found():
    resp = client.get("/api/tasks/task-doesnotexist-99999")
    assert resp.status_code == 404


# ─── Agents ───────────────────────────────────────────────────────────────────

def test_list_agents():
    db = get_test_db()
    _seed_agent(db, "agent-agy-01", "agy")
    _seed_agent(db, "agent-claude-01", "anthropic")
    _seed_agent(db, "agent-codex-01", "openai")

    resp = client.get("/api/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3
    # Must be dynamic — not hardcoded to 3
    assert len(data["items"]) >= 1


def test_get_agent():
    db = get_test_db()
    aid = _seed_agent(db, "agent-agy-test", "agy")
    resp = client.get(f"/api/agents/{aid}")
    assert resp.status_code == 200
    assert resp.json()["agent_id"] == aid
    assert isinstance(resp.json()["capabilities"], list)


def test_get_agent_not_found():
    resp = client.get("/api/agents/agent-nonexistent")
    assert resp.status_code == 404


def test_elastic_agent_support():
    """UI must support 1–4 agents without hardcoding."""
    db = get_test_db()
    for i in range(4):
        _seed_agent(db, f"agent-elastic-{i}", f"provider-{i}")
    resp = client.get("/api/agents")
    data = resp.json()
    assert data["total"] >= 4


# ─── Findings ─────────────────────────────────────────────────────────────────

def test_list_findings():
    db = get_test_db()
    _seed_finding(db)
    resp = client.get("/api/findings")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_list_findings_state_filter():
    db = get_test_db()
    _seed_finding(db, state="CONFIRMED")
    resp = client.get("/api/findings?state=CONFIRMED")
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["state"] == "CONFIRMED"


def test_get_finding_detail():
    db = get_test_db()
    fid = _seed_finding(db)
    resp = client.get(f"/api/findings/{fid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["finding_id"] == fid
    assert "evidence_ids" in data
    assert "affected_locations" in data


def test_finding_state_not_mutable_from_api():
    """API provides no endpoint to directly mutate finding state."""
    db = get_test_db()
    fid = _seed_finding(db, state="OPEN")
    # No PATCH/PUT endpoint should exist for findings
    resp = client.patch(f"/api/findings/{fid}", json={"state": "CONFIRMED"})
    assert resp.status_code in (404, 405, 422)


# ─── Evidence ─────────────────────────────────────────────────────────────────

def test_list_evidence():
    db = get_test_db()
    _seed_evidence(db)
    resp = client.get("/api/evidence")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_get_evidence_detail():
    db = get_test_db()
    eid = _seed_evidence(db)
    resp = client.get(f"/api/evidence/{eid}")
    assert resp.status_code == 200
    data = resp.json()
    # Evidence viewer must expose these fields
    assert "raw_hash" in data
    assert "canonical_hash" in data
    assert "semantic_identity" in data
    assert "source_tool" in data
    assert "provenance" in data


def test_evidence_not_fabricatable():
    """No POST endpoint should allow fabricating evidence."""
    resp = client.post("/api/evidence", json={
        "evidence_id": "fake-ev-001",
        "source_tool": "fake",
        "raw_hash": "deadbeef",
    })
    assert resp.status_code in (404, 405, 422)


def test_sensitive_data_redaction():
    """Provenance with secrets should be redacted."""
    db = get_test_db()
    eid = f"ev-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO evidence (evidence_id, task_id, run_id, agent_id, source_type, "
            "raw_hash, canonical_hash, semantic_fingerprint, environment_fingerprint, "
            "exit_status, provenance, schema_version, finding_id, source_tool, timestamp) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, "t1", "r1", "a1", "TOOL", "h1", "h2", "sf", "ef", 0,
             '{"api_key": "sk-secret-12345", "host": "example.com"}', "1.0", None, "tool", now)
        )
    resp = client.get(f"/api/evidence/{eid}")
    assert resp.status_code == 200
    prov = resp.json()["provenance"]
    assert prov.get("api_key") == "***REDACTED***"
    assert prov.get("host") == "example.com"


# ─── Timeline ─────────────────────────────────────────────────────────────────

def test_timeline_returns_events():
    resp = client.get("/api/timeline?limit=50")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data


def test_timeline_filter_by_event_type():
    resp = client.get("/api/timeline?event_type=TASK_CREATED&limit=10")
    assert resp.status_code == 200


def test_timeline_pagination():
    resp1 = client.get("/api/timeline?limit=5&offset=0")
    resp2 = client.get("/api/timeline?limit=5&offset=5")
    assert resp1.status_code == 200
    assert resp2.status_code == 200


# ─── Repository ───────────────────────────────────────────────────────────────

def test_list_repositories():
    resp = client.get("/api/repositories")
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_list_analysis_units():
    resp = client.get("/api/analysis-units")
    assert resp.status_code == 200


def test_get_analysis_unit_not_found():
    resp = client.get("/api/analysis-units/unit-nonexistent")
    assert resp.status_code == 404


def test_security_surface_returns_empty_for_unknown_unit():
    resp = client.get("/api/analysis-units/unit-unknown/security-surface")
    # Should return empty surface, not 404
    assert resp.status_code == 200
    data = resp.json()
    assert "surface_id" in data


# ─── Validation & Reproducers ─────────────────────────────────────────────────

def test_list_validations():
    resp = client.get("/api/validation")
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_list_reproducers():
    resp = client.get("/api/reproducers")
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_validation_not_found():
    resp = client.get("/api/validation/val-doesnotexist")
    assert resp.status_code == 404


# ─── Controls ─────────────────────────────────────────────────────────────────

def test_analyst_action_pause_task():
    db = get_test_db()
    tid = _seed_task(db, status="RUNNING")
    resp = client.post("/api/controls/action", json={
        "action": "pause",
        "target_type": "task",
        "target_id": tid,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] is True
    assert data["control_plane_decision"] == "ACCEPTED"
    assert data["event_id"] is not None


def test_analyst_action_cancel_task():
    db = get_test_db()
    tid = _seed_task(db, status="RUNNING")
    resp = client.post("/api/controls/action", json={
        "action": "cancel",
        "target_type": "task",
        "target_id": tid,
    })
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True


def test_analyst_action_creates_audit_event():
    db = get_test_db()
    tid = _seed_task(db, status="RUNNING")
    client.post("/api/controls/action", json={
        "action": "pause",
        "target_type": "task",
        "target_id": tid,
    })
    # Verify event was persisted
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE event_type='ANALYST_ACTION' AND entity_id=?",
            (tid,)
        ).fetchone()
    assert row is not None


def test_analyst_action_invalid_action():
    resp = client.post("/api/controls/action", json={
        "action": "delete_all_findings",
        "target_type": "task",
        "target_id": "task-x",
    })
    assert resp.status_code == 400


def test_analyst_action_wrong_target_type():
    resp = client.post("/api/controls/action", json={
        "action": "pause",
        "target_type": "finding",
        "target_id": "finding-x",
    })
    assert resp.status_code == 400


def test_analyst_action_nonexistent_target():
    resp = client.post("/api/controls/action", json={
        "action": "pause",
        "target_type": "task",
        "target_id": "task-doesnotexist-999",
    })
    assert resp.status_code == 404


def test_high_impact_action_requires_reason():
    db = get_test_db()
    tid = _seed_task(db)
    resp = client.post("/api/controls/action", json={
        "action": "approve",
        "target_type": "task",
        "target_id": tid,
        # No reason provided
    })
    assert resp.status_code == 200
    assert resp.json()["accepted"] is False
    assert resp.json()["control_plane_decision"] == "REJECTED"


def test_no_direct_finding_state_mutation():
    """Finding state cannot be mutated through the controls endpoint."""
    db = get_test_db()
    fid = _seed_finding(db, state="OPEN")
    # 'pause' is not valid for findings
    resp = client.post("/api/controls/action", json={
        "action": "pause",
        "target_type": "finding",
        "target_id": fid,
    })
    assert resp.status_code == 400


def test_feedback_valid():
    db = get_test_db()
    fid = _seed_finding(db)
    resp = client.post("/api/controls/feedback", json={
        "finding_id": fid,
        "label": "FALSE_POSITIVE",
        "comment": "Reviewed manually — not a real issue.",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] is True
    assert data["feedback_id"] is not None


def test_feedback_invalid_label():
    db = get_test_db()
    fid = _seed_finding(db)
    resp = client.post("/api/controls/feedback", json={
        "finding_id": fid,
        "label": "TOTALLY_FAKE_LABEL",
    })
    assert resp.status_code == 400


def test_feedback_does_not_modify_finding():
    """Feedback event is created, but the finding state remains unchanged."""
    db = get_test_db()
    fid = _seed_finding(db, state="OPEN")
    client.post("/api/controls/feedback", json={
        "finding_id": fid,
        "label": "CONFIRMED",
    })
    resp = client.get(f"/api/findings/{fid}")
    # Finding state must still be OPEN — feedback doesn't change it
    assert resp.json()["state"] == "OPEN"


def test_audit_log_returns_events():
    resp = client.get("/api/controls/audit")
    assert resp.status_code == 200
    assert "items" in resp.json()


# ─── Authorization ────────────────────────────────────────────────────────────

def test_invalid_session_token():
    resp = client.get(
        "/api/tasks",
        headers={"X-Session-Token": "totally-invalid-token-xyz"},
    )
    # Should be rejected with 401
    assert resp.status_code == 401


def test_openapi_schema_accessible():
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "openapi" in schema
    assert "paths" in schema


# ─── Static UI & Console Routes ───────────────────────────────────────────────

def test_root_serves_console_ui():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "LLMorch" in resp.text


def test_favicon_served():
    resp = client.get("/favicon.ico")
    assert resp.status_code == 200
    assert len(resp.content) > 0


def test_vite_svg_served():
    resp = client.get("/vite.svg")
    assert resp.status_code == 200


def test_spa_client_route_fallback():
    # Any client-side SPA subpath (non-api) should serve index.html
    resp = client.get("/timeline")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "LLMorch" in resp.text


def test_nonexistent_api_route_returns_404():
    # API paths that don't exist must still 404, not fallback to index.html
    resp = client.get("/api/this_endpoint_does_not_exist")
    assert resp.status_code == 404

