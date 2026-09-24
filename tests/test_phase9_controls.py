"""
LLMorch Phase 9 — Controls plane authority tests.

Verifies that:
- All analyst actions go through the API → control-plane pipeline
- Finding state cannot be mutated directly from UI
- Evidence cannot be fabricated from UI
- Audit events are always created
- High-impact operations require explicit reason
- Unauthorized mutations are rejected
"""

import os
import uuid
import json
import pytest

_TEST_DB = f"/tmp/llmorch_p9_ctrl_{uuid.uuid4().hex[:8]}.db"
os.environ.setdefault("LLMORCH_DB_PATH", _TEST_DB)

from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app, raise_server_exceptions=True)


def get_db():
    from history.database import get_db_path, DatabaseService
    return DatabaseService(get_db_path())


def seed_task(db, status="RUNNING"):
    tid = f"task-ctrl-{uuid.uuid4().hex[:8]}"
    now = "2026-01-01T00:00:00+00:00"
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO tasks (task_id,workflow_id,parent_task_id,objective,inputs,"
            "dependencies,required_capabilities,preferred_roles,risk_level,workspace_policy,"
            "tool_policy,budget,status,assigned_agent_id,retry_count,acceptance_criteria,"
            "result_ref,schema_version,created_at,started_at,completed_at) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tid,"wf1",None,"obj","[]","[]","[]","[]","LOW","{}","{}","{}",
             status,"agent-agy-01",0,"[]",None,"1.0",now,now,None)
        )
    return tid


def seed_finding(db, state="OPEN"):
    fid = f"finding-ctrl-{uuid.uuid4().hex[:8]}"
    now = "2026-01-01T00:00:00+00:00"
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO findings (finding_id,fingerprint,hypothesis,locations,"
            "supporting_evidence,contradicting_evidence,validation_method,validator_result,"
            "state,lineage,timestamps,schema_version,task_id,created_at,updated_at) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (fid,uuid.uuid4().hex,"hypothesis","[]","[]","[]",None,None,
             state,"{}","{}","1.0",None,now,now)
        )
    return fid


# ─── Finding Authority ────────────────────────────────────────────────────────

def test_finding_state_only_changes_via_validator():
    """
    Browser request does NOT mutate finding state.
    Only the validator/decision service path is authoritative.
    """
    db = get_db()
    fid = seed_finding(db, state="OPEN")

    # Attempt 1: PATCH endpoint (should not exist)
    r = client.patch(f"/api/findings/{fid}", json={"state": "CONFIRMED"})
    assert r.status_code in (404, 405, 422), f"Unexpected: {r.status_code}"

    # Attempt 2: PUT endpoint (should not exist)
    r = client.put(f"/api/findings/{fid}", json={"state": "CONFIRMED"})
    assert r.status_code in (404, 405, 422), f"Unexpected: {r.status_code}"

    # Attempt 3: POST to findings (should not exist)
    r = client.post("/api/findings", json={"finding_id": fid, "state": "CONFIRMED"})
    assert r.status_code in (404, 405, 422), f"Unexpected: {r.status_code}"

    # State in DB is still OPEN
    r = client.get(f"/api/findings/{fid}")
    assert r.status_code == 200
    assert r.json()["state"] == "OPEN"


def test_finding_feedback_does_not_change_state():
    """Feedback is recorded but finding state is unchanged."""
    db = get_db()
    fid = seed_finding(db, state="OPEN")

    r = client.post("/api/controls/feedback", json={
        "finding_id": fid,
        "label": "FALSE_POSITIVE",
        "comment": "Reviewed",
    })
    assert r.status_code == 200
    assert r.json()["accepted"] is True

    # State still OPEN
    r = client.get(f"/api/findings/{fid}")
    assert r.json()["state"] == "OPEN"


def test_confirming_via_controls_not_allowed():
    """Controls endpoint cannot set finding state to CONFIRMED."""
    db = get_db()
    fid = seed_finding(db, state="OPEN")
    r = client.post("/api/controls/action", json={
        "action": "pause",
        "target_type": "finding",
        "target_id": fid,
    })
    assert r.status_code == 400


# ─── Evidence Authority ───────────────────────────────────────────────────────

def test_evidence_creation_not_possible_from_api():
    """No POST/PUT endpoint exists for evidence."""
    fake = {
        "evidence_id": "fake-ev-001",
        "source_tool": "fake_tool",
        "raw_hash": "deadbeef",
        "canonical_hash": "cafebabe",
        "task_id": "task-fake",
        "run_id": "run-fake",
        "agent_id": "agent-fake",
    }
    r = client.post("/api/evidence", json=fake)
    assert r.status_code in (404, 405, 422)

    r = client.put("/api/evidence/fake-ev-001", json=fake)
    assert r.status_code in (404, 405, 422)

    r = client.patch("/api/evidence/fake-ev-001", json=fake)
    assert r.status_code in (404, 405, 422)


# ─── Audit Trail ──────────────────────────────────────────────────────────────

def test_every_control_action_creates_audit_event():
    """Pause, resume, cancel all create auditable events."""
    db = get_db()

    actions_and_states = [
        ("pause", "RUNNING"),
        ("resume", "PAUSED"),
        ("cancel", "RUNNING"),
    ]

    for action, status in actions_and_states:
        tid = seed_task(db, status=status)
        r = client.post("/api/controls/action", json={
            "action": action,
            "target_type": "task",
            "target_id": tid,
        })
        assert r.status_code == 200
        assert r.json()["accepted"] is True

        # Audit event persisted
        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM events WHERE event_type='ANALYST_ACTION' AND entity_id=?",
                (tid,)
            ).fetchone()
        assert row is not None, f"Audit event missing for action={action}"


def test_feedback_creates_audit_event():
    db = get_db()
    fid = seed_finding(db)
    client.post("/api/controls/feedback", json={
        "finding_id": fid,
        "label": "CONFIRMED",
    })
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE event_type='FEEDBACK_SUBMITTED' AND entity_id=?",
            (fid,)
        ).fetchone()
    assert row is not None


def test_audit_log_accessible():
    r = client.get("/api/controls/audit")
    assert r.status_code == 200
    assert "items" in r.json()


# ─── High Impact Gate ─────────────────────────────────────────────────────────

def test_approve_without_reason_rejected():
    db = get_db()
    tid = seed_task(db)
    r = client.post("/api/controls/action", json={
        "action": "approve",
        "target_type": "task",
        "target_id": tid,
    })
    assert r.json()["accepted"] is False
    assert r.json()["control_plane_decision"] == "REJECTED"


def test_approve_with_reason_accepted():
    db = get_db()
    tid = seed_task(db)
    r = client.post("/api/controls/action", json={
        "action": "approve",
        "target_type": "task",
        "target_id": tid,
        "reason": "Manually reviewed and approved for execution.",
    })
    assert r.json()["accepted"] is True
    assert r.json()["control_plane_decision"] == "ACCEPTED"


# ─── No Direct DB Access ──────────────────────────────────────────────────────

def test_no_raw_sql_endpoint():
    """API does not expose a raw SQL execution endpoint."""
    r = client.post("/api/query", json={"sql": "SELECT * FROM findings"})
    assert r.status_code in (404, 405)

    r = client.get("/api/db")
    assert r.status_code in (404, 405)


def test_no_sqlite_file_download():
    """API does not expose the raw SQLite file."""
    r = client.get("/api/llmorch.db")
    assert r.status_code in (404, 405)

    r = client.get("/history/llmorch.db")
    assert r.status_code in (404, 405)


# ─── No Direct Worker Access ──────────────────────────────────────────────────

def test_no_direct_subprocess_endpoint():
    """API does not expose endpoints to shell out to agent processes."""
    r = client.post("/api/exec", json={"command": "claude -p 'test'"})
    assert r.status_code in (404, 405)

    r = client.post("/api/shell", json={"cmd": "ls"})
    assert r.status_code in (404, 405)


# ─── Stale State Rejection ────────────────────────────────────────────────────

def test_action_on_nonexistent_entity_rejected():
    """Actions on entities that don't exist are rejected with 404."""
    r = client.post("/api/controls/action", json={
        "action": "pause",
        "target_type": "task",
        "target_id": "task-stale-phantom-id",
    })
    assert r.status_code == 404


# ─── Session Security ─────────────────────────────────────────────────────────

def test_invalid_token_rejected():
    r = client.post(
        "/api/controls/action",
        json={"action": "pause", "target_type": "task", "target_id": "task-x"},
        headers={"X-Session-Token": "bad-token-xyz"},
    )
    assert r.status_code == 401


def test_sensitive_local_paths_not_exposed():
    """API responses must not contain raw filesystem paths to secrets."""
    r = client.get("/api/health")
    text = r.text
    assert "/root/.ssh" not in text
    assert "id_rsa" not in text
    assert "ANTHROPIC_API_KEY" not in text
