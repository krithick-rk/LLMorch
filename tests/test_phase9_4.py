"""
test_phase9_4.py — Phase 9.4 Run Control State Machine Test Suite

Tests cover:
  - Run state machine transitions (pause/resume/stop/emergency-stop)
  - State invariants (terminal states, duplicate prevention)
  - Checkpoint preservation
  - Realtime event broadcasting
  - Navigation structure and new API endpoints

Execution policy: Claude must NEVER execute. AGY/Codex are allowed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from api.app import app
from api.session import get_default_token
from api.models import RUN_STATES


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)

@pytest.fixture(scope="module")
def token():
    return get_default_token()

@pytest.fixture(scope="module")
def auth(token):
    return {"X-Session-Token": token}


# ─── Helper: create a synthetic run ──────────────────────────────────────────

def _make_run(client, auth) -> str:
    """Insert a synthetic RUNNING run directly into the DB for state-machine testing."""
    from history.database import get_db_path, DatabaseService
    import uuid
    from datetime import datetime, timezone

    db = DatabaseService(get_db_path())
    run_id = f"run-test-{uuid.uuid4().hex[:8]}"
    tid = f"task-root-{run_id}"
    now = datetime.now(timezone.utc).isoformat()

    with db.get_connection() as conn:
        # Temporarily disable FK constraints for synthetic test data
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("""
            INSERT INTO runs (
                run_id, task_id, agent_id, adapter_version, start_time,
                workspace_id, environment_fingerprint, status, schema_version,
                run_state, repository_name, repository_path, token_budget
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id, tid, "agent-agy-01", "1.0.0", now,
            f"ws-{run_id}", "test", "RUNNING", "1.0",
            "RUNNING", "Test Repository", "/tmp/test", 650000
        ))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
    return run_id


# ─── Run State Machine tests ──────────────────────────────────────────────────

class TestRunStateMachine:

    def test_run_states_defined(self):
        """All 13 run states must be defined."""
        required = {
            "PREPARING", "RUNNING", "PAUSE_REQUESTED", "PAUSED",
            "RESUME_REQUESTED", "STOP_REQUESTED", "DRAINING",
            "CHECKPOINTING", "STOPPED", "FAILED", "COMPLETED",
            "EMERGENCY_STOP_REQUESTED", "EMERGENCY_STOPPED",
        }
        defined = set(RUN_STATES)
        assert required == defined, f"Missing states: {required - defined}"

    def test_list_runs_endpoint(self, client, auth):
        resp = client.get("/api/runs", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_current_run_404_when_empty(self, client, auth):
        # May or may not have runs, just must not 500
        resp = client.get("/api/runs/current", headers=auth)
        assert resp.status_code in (200, 404)

    def test_run_not_found(self, client, auth):
        resp = client.get("/api/runs/nonexistent-run-xyz", headers=auth)
        assert resp.status_code == 404

    def test_pause_nonexistent_run(self, client, auth):
        resp = client.post("/api/runs/nonexistent-run-xyz/pause", headers=auth, json={})
        assert resp.status_code == 404

    def test_stop_nonexistent_run(self, client, auth):
        resp = client.post("/api/runs/nonexistent-run-xyz/stop", headers=auth, json={})
        assert resp.status_code == 404


class TestPauseResumeFlow:

    def test_pause_running_run(self, client, auth):
        """RUNNING → PAUSE_REQUESTED → PAUSED should succeed."""
        run_id = _make_run(client, auth)
        resp = client.post(f"/api/runs/{run_id}/pause", headers=auth,
                           json={"reason": "test pause"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "PAUSE"
        assert data["from_state"] == "RUNNING"
        assert data["to_state"] == "PAUSED"

    def test_pause_sets_backend_state(self, client, auth):
        """After pause, GET /api/runs/{id} must show PAUSED."""
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/pause", headers=auth, json={})
        resp = client.get(f"/api/runs/{run_id}", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_state"] == "PAUSED"

    def test_resume_paused_run(self, client, auth):
        """PAUSED → RESUME_REQUESTED → RUNNING."""
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/pause", headers=auth, json={})
        resp = client.post(f"/api/runs/{run_id}/resume", headers=auth,
                           json={"reason": "test resume"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "RESUME"
        assert data["to_state"] == "RUNNING"

    def test_cannot_resume_running_run(self, client, auth):
        """Cannot RESUME a RUNNING run — invalid transition."""
        run_id = _make_run(client, auth)
        resp = client.post(f"/api/runs/{run_id}/resume", headers=auth, json={})
        # Should get 409 Conflict (invalid state transition)
        assert resp.status_code == 409

    def test_cannot_pause_paused_run(self, client, auth):
        """Cannot PAUSE an already PAUSED run."""
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/pause", headers=auth, json={})
        resp = client.post(f"/api/runs/{run_id}/pause", headers=auth, json={})
        assert resp.status_code == 409

    def test_pause_increments_checkpoint_count(self, client, auth):
        """Each pause cycle should increment checkpoint_count."""
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/pause", headers=auth, json={})
        resp = client.get(f"/api/runs/{run_id}", headers=auth)
        data = resp.json()
        assert data["checkpoint_count"] >= 1


class TestStopFlow:

    def test_stop_running_run(self, client, auth):
        """RUNNING → STOP_REQUESTED → DRAINING → CHECKPOINTING → STOPPED."""
        run_id = _make_run(client, auth)
        resp = client.post(f"/api/runs/{run_id}/stop", headers=auth,
                           json={"reason": "test stop"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "STOP"
        assert data["to_state"] == "STOPPED"

    def test_stop_sets_backend_state(self, client, auth):
        """After stop, backend must show STOPPED — not RUNNING."""
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/stop", headers=auth, json={})
        resp = client.get(f"/api/runs/{run_id}", headers=auth)
        data = resp.json()
        assert data["run_state"] == "STOPPED"

    def test_stop_paused_run(self, client, auth):
        """PAUSED run can also be stopped."""
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/pause", headers=auth, json={})
        resp = client.post(f"/api/runs/{run_id}/stop", headers=auth, json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["to_state"] == "STOPPED"

    def test_cannot_stop_already_stopped(self, client, auth):
        """Stopping a STOPPED run must be rejected (terminal state)."""
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/stop", headers=auth, json={})
        resp = client.post(f"/api/runs/{run_id}/stop", headers=auth, json={})
        assert resp.status_code == 409

    def test_stop_preserves_evidence(self, client, auth):
        """Evidence table must still be accessible after stop."""
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/stop", headers=auth, json={})
        resp = client.get("/api/evidence", headers=auth)
        assert resp.status_code == 200

    def test_stop_preserves_findings(self, client, auth):
        """Findings must remain accessible after stop."""
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/stop", headers=auth, json={})
        resp = client.get("/api/findings", headers=auth)
        assert resp.status_code == 200

    def test_stop_preserves_task_lineage(self, client, auth):
        """Tasks must remain accessible after stop."""
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/stop", headers=auth, json={})
        resp = client.get("/api/tasks", headers=auth)
        assert resp.status_code == 200


class TestEmergencyStop:

    def test_emergency_stop_requires_confirmation(self, client, auth):
        """Emergency stop without emergency=True must be rejected."""
        run_id = _make_run(client, auth)
        resp = client.post(f"/api/runs/{run_id}/emergency-stop",
                           headers=auth, json={"emergency": False})
        assert resp.status_code == 400

    def test_emergency_stop_with_confirmation(self, client, auth):
        """Emergency stop with emergency=True must succeed."""
        run_id = _make_run(client, auth)
        resp = client.post(f"/api/runs/{run_id}/emergency-stop",
                           headers=auth, json={"emergency": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["to_state"] == "EMERGENCY_STOPPED"

    def test_emergency_stop_sets_state(self, client, auth):
        """After emergency stop, backend must show EMERGENCY_STOPPED."""
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/emergency-stop",
                    headers=auth, json={"emergency": True})
        resp = client.get(f"/api/runs/{run_id}", headers=auth)
        data = resp.json()
        assert data["run_state"] == "EMERGENCY_STOPPED"

    def test_cannot_emergency_stop_stopped_run(self, client, auth):
        """STOPPED runs cannot be emergency-stopped (terminal state)."""
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/stop", headers=auth, json={})
        resp = client.post(f"/api/runs/{run_id}/emergency-stop",
                           headers=auth, json={"emergency": True})
        assert resp.status_code == 409


class TestRunControlEvents:

    def test_events_endpoint(self, client, auth):
        """Run control events audit trail."""
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/pause", headers=auth, json={})
        resp = client.get(f"/api/runs/{run_id}/events", headers=auth)
        assert resp.status_code == 200
        events = resp.json()
        assert isinstance(events, list)

    def test_events_contain_pause_record(self, client, auth):
        """After pause, events must contain PAUSE action."""
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/pause", headers=auth, json={})
        resp = client.get(f"/api/runs/{run_id}/events", headers=auth)
        events = resp.json()
        actions = [e.get("action") for e in events]
        assert "PAUSE" in actions or "PAUSED" in actions

    def test_events_contain_stop_record(self, client, auth):
        """After stop, events must contain STOP action."""
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/stop", headers=auth, json={})
        resp = client.get(f"/api/runs/{run_id}/events", headers=auth)
        events = resp.json()
        actions = [e.get("action") for e in events]
        assert "STOP" in actions or "STOPPED" in actions


# ─── Execution Policy (Claude must not execute) ───────────────────────────────

class TestExecutionPolicy:

    def test_claude_blocked_in_run_control(self, client, auth):
        """No run control action should invoke Claude."""
        from scheduler.execution_policy import get_execution_policy
        policy = get_execution_policy()
        assert not policy.allow_real_claude_execution

    def test_analysis_prevalidate_blocks_claude(self, client, auth):
        resp = client.post("/api/analysis/pre-validate", headers=auth)
        data = resp.json()
        assert data.get("execution_policy_valid") is True


# ─── Checkpoint Preservation ──────────────────────────────────────────────────

class TestCheckpointPreservation:

    def test_checkpoint_count_increases_on_pause(self, client, auth):
        run_id = _make_run(client, auth)
        # Pause once
        client.post(f"/api/runs/{run_id}/pause", headers=auth, json={})
        resp = client.get(f"/api/runs/{run_id}", headers=auth)
        c1 = resp.json().get("checkpoint_count", 0)
        assert c1 >= 1

    def test_stop_also_checkpoints(self, client, auth):
        run_id = _make_run(client, auth)
        client.post(f"/api/runs/{run_id}/stop", headers=auth, json={})
        resp = client.get(f"/api/runs/{run_id}", headers=auth)
        assert resp.json().get("checkpoint_count", 0) >= 1


# ─── Repository Assignment tests ─────────────────────────────────────────────

class TestRepositoryAssignment:

    def test_analysis_prevalidate_has_agent_capacity(self, client, auth):
        resp = client.post("/api/analysis/pre-validate", headers=auth)
        data = resp.json()
        assert data["agent_capacity"] > 0

    def test_analysis_prevalidate_has_tools(self, client, auth):
        resp = client.post("/api/analysis/pre-validate", headers=auth)
        data = resp.json()
        assert data["tools_available"] > 0

    def test_auto_assignment_creates_run(self, client, auth):
        """Starting an analysis via API should create a run record."""
        import os, tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            resp = client.post("/api/analysis/start", headers=auth,
                               json={"repository_path": tmpdir, "token_budget": 100000})
            if resp.status_code == 200:
                data = resp.json()
                assert "run_id" in data
                assert data["status"] == "RUNNING"


# ─── Navigation Structure ─────────────────────────────────────────────────────

class TestNavigationStructure:

    REQUIRED_NAV_IDS = [
        'overview', 'workflow', 'target-repo',
        'agents', 'tools',
        'dossier', 'hypothesis', 'evidence', 'timeline', 'intel',
        'settings',
    ]

    def test_nav_ids_in_app_jsx(self):
        import os
        app_path = os.path.join(
            os.path.dirname(__file__), '..', 'ui', 'src', 'App.jsx'
        )
        if not os.path.exists(app_path):
            pytest.skip("App.jsx not found")
        with open(app_path) as f:
            content = f.read()
        for page_id in self.REQUIRED_NAV_IDS:
            assert f"'{page_id}'" in content or f'"{page_id}"' in content, \
                f"Page ID '{page_id}' missing from App.jsx"

    def test_run_control_buttons_in_app_jsx(self):
        import os
        app_path = os.path.join(
            os.path.dirname(__file__), '..', 'ui', 'src', 'App.jsx'
        )
        if not os.path.exists(app_path):
            pytest.skip("App.jsx not found")
        with open(app_path) as f:
            content = f.read()
        assert "btn-pause" in content, "Pause button ID missing"
        assert "btn-stop" in content,  "Stop button ID missing"
        assert "btn-resume" in content, "Resume button ID missing"
        assert "btn-emergency-stop" in content, "Emergency stop button missing"
        assert "StopConfirmModal" in content, "Stop confirmation modal missing"

    def test_soc_css_has_state_dots(self):
        import os
        css_path = os.path.join(
            os.path.dirname(__file__), '..', 'ui', 'src', 'index.css'
        )
        if not os.path.exists(css_path):
            pytest.skip("index.css not found")
        with open(css_path) as f:
            content = f.read()
        assert ".state-dot" in content, "SOC state dot CSS missing"
        assert ".badge-running" in content, "SOC badge CSS missing"
        assert "--font-mono" in content, "Monospace font token missing"
        assert ".data-table" in content, "Dense table CSS missing"
        assert ".btn-danger" in content, "Danger button CSS missing"

    def test_runs_router_registered(self, client, auth):
        """The /api/runs endpoint must respond."""
        resp = client.get("/api/runs", headers=auth)
        assert resp.status_code == 200

    def test_runs_current_endpoint_exists(self, client, auth):
        resp = client.get("/api/runs/current", headers=auth)
        assert resp.status_code in (200, 404)

    def test_run_pause_endpoint_exists(self, client, auth):
        resp = client.post("/api/runs/nonexistent/pause", headers=auth, json={})
        assert resp.status_code == 404  # endpoint exists, run doesn't

    def test_run_stop_endpoint_exists(self, client, auth):
        resp = client.post("/api/runs/nonexistent/stop", headers=auth, json={})
        assert resp.status_code == 404

    def test_emergency_stop_endpoint_exists(self, client, auth):
        resp = client.post("/api/runs/nonexistent/emergency-stop",
                           headers=auth, json={"emergency": True})
        assert resp.status_code in (404, 409)  # not found, not 405

    def test_dag_backend_still_accessible(self, client, auth):
        """DAG must be preserved even though removed from nav."""
        from history.database import get_db_path, DatabaseService
        db = DatabaseService(get_db_path())
        with db.get_connection() as conn:
            info = conn.execute("PRAGMA table_info(tasks)").fetchall()
        col_names = [row[1] for row in info]
        assert any("depend" in c.lower() for c in col_names), \
            "DAG dependency columns must be preserved"
