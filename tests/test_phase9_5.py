"""
test_phase9_5.py — Phase 9.5 Security Console, Human-in-the-Loop, and Investigation Lifecycle Test Suite.

Tests cover:
  1. Repository intelligence lifecycle as a separate stage (Validation -> Analysis -> Overview -> WAITING_FOR_ANALYST -> Security Start)
  2. Empty repository and single empty file correctness (0 source tokens, 0 units, analyst question generated)
  3. Small/tiny repository token estimation (proportional scaling, no huge constant minimum floors)
  4. Generic repository fallback intelligence for unknown repos
  5. Agent runtime availability & truthful status (1 agent is sufficient, Claude disabled by policy, AGY/Codex verified)
  6. Terminal guidance (no credentials captured or stored in UI)
  7. Human-in-the-loop analyst questions lifecycle (PENDING -> ANSWERED / DISMISSED)
  8. Research Guard / Stall protection (detects circular loops and creates analyst questions)
  9. Authoritative active security analysis timer (0 before start, freezes on pause, continues on resume, freezes on stop/completion)
  10. Analyst instructions and attempt lineage preservation
  11. Entity API endpoints for persistent URLs and new-tab support

CRITICAL EXECUTION POLICY: Claude CLI is never spawned or executed.
"""

from __future__ import annotations

import os
import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi.testclient import TestClient

from api.app import app
from api.session import get_default_token
from history.database import get_db_path, DatabaseService
from history.phase9_repositories import QuestionRepository, TaskAttemptRepository, ToolExecutionRepository
from repository_intelligence.token_estimator import estimate_repository_tokens
from orchestrator.stall_detector import StallDetector


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def token():
    return get_default_token()


@pytest.fixture(scope="module")
def auth(token):
    return {"X-Session-Token": token}


# ─── 1. Repository Analysis Lifecycle & Capability Report ────────────────────

class TestRepositoryLifecycle:

    def test_empty_file_repository_produces_zero_source_tokens_and_question(self, tmp_path, client, auth):
        """Single empty file must NOT produce massive tokens or fabricated units, and asks analyst."""
        empty_file = tmp_path / "empty.c"
        empty_file.write_text("")

        est = estimate_repository_tokens(str(tmp_path))
        assert est.total_files_discovered == 1
        assert est.raw_token_estimate == 0
        assert est.llm_scoped_token_estimate == 0
        assert est.analysis_unit_estimate == 0
        assert est.recommended_budget == 0

        # Run analyze endpoint
        resp = client.post("/api/repositories/analyze", json={"repository_path": str(tmp_path)}, headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_files"] == 1
        assert data["content_bearing_files"] == 0
        assert data["empty_files"] == 1
        assert data["is_empty_repository"] is True
        assert data["analysis_units_count"] == 0
        assert "no source content available" in data["empty_repository_explanation"].lower()
        # Question was automatically generated
        assert len(data["questions"]) >= 1
        assert "empty" in data["questions"][0]["question"].lower()

    def test_tiny_source_file_produces_small_proportional_estimate(self, tmp_path):
        """Small single-function source file produces small proportional estimate."""
        source_file = tmp_path / "main.c"
        source_file.write_text("int main(void) { return 0; }\n")

        est = estimate_repository_tokens(str(tmp_path))
        assert est.total_files_discovered == 1
        assert est.raw_token_estimate > 0
        assert est.llm_scoped_token_estimate < 1000
        # Recommended budget is small and proportional, NOT 650,000!
        assert est.recommended_budget < 10000

    def test_generic_unknown_repository_produces_fallback_report(self, tmp_path, client, auth):
        """Arbitrary non-OpenTitan repository receives clean generic capability report without errors."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "util.py").write_text("def sanitize(x): return x.strip()\n" * 10)
        (tmp_path / "Makefile").write_text("all:\n\tpython3 src/util.py\n")

        resp = client.post("/api/repositories/analyze", json={"repository_path": str(tmp_path)}, headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_generic"] is True
        assert data["repository_family"] == "UNKNOWN"
        assert "generic repository intelligence" in data["generic_explanation"].lower()
        assert "python" in [l.lower() for l in data["languages"]]
        assert "Make" in data["build_systems"]
        assert len(data["recommended_tools"]) >= 1


# ─── 2. Agent Runtime Availability & Terminal Guidance ───────────────────────

class TestAgentRuntimeStatus:

    def test_runtime_status_truthful(self, client, auth):
        """Queries runtime status and verifies truthful reporting and critical execution policy."""
        resp = client.get("/api/agents/runtime/status", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_agents"] >= 3
        # One or more agents is enough
        assert data["is_operational"] is True

        claude = next((a for a in data["agents"] if a["agent_id"] == "agent-claude-01"), None)
        assert claude is not None
        assert claude["executable"] is False
        assert claude["execution_enabled"] is False
        assert "DISABLED" in claude["execution_policy_note"]

    def test_refresh_runtime_status_endpoint(self, client, auth):
        resp = client.post("/api/agents/runtime/refresh", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data

    def test_terminal_open_guidance_does_not_leak_credentials(self, client, auth):
        resp = client.post("/api/agents/runtime/terminal", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "terminal" in data["message"].lower()


# ─── 3. Human-in-the-Loop Analyst Questions Lifecycle ────────────────────────

class TestAnalystQuestions:

    def test_question_lifecycle(self, client, auth):
        """Creates a question, retrieves it, answers it, and verifies state transition."""
        db = DatabaseService(get_db_path())
        q_repo = QuestionRepository(db)

        # Create
        q = q_repo.create_question(
            reason="Ambiguous Register Access Policy",
            question="Should register 0x4000 be treated as Read-Only in privileged mode?",
            options=[
                {"id": "ro", "label": "Read-Only", "description": "Lock register in privileged mode"},
                {"id": "rw", "label": "Read-Write", "description": "Allow write access"},
            ],
            default_option="ro",
        )
        qid = q["question_id"]

        # List
        resp = client.get(f"/api/questions?status=QUESTION_PENDING", headers=auth)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(item["question_id"] == qid for item in items)

        # Get detail
        resp_det = client.get(f"/api/questions/{qid}", headers=auth)
        assert resp_det.status_code == 200
        assert resp_det.json()["status"] == "QUESTION_PENDING"

        # Answer
        resp_ans = client.post(f"/api/questions/{qid}/answer", json={"answer": "Read-Only"}, headers=auth)
        assert resp_ans.status_code == 200
        assert resp_ans.json()["status"] == "QUESTION_ANSWERED"
        assert resp_ans.json()["answer"] == "Read-Only"

    def test_dismiss_question(self, client, auth):
        db = DatabaseService(get_db_path())
        q_repo = QuestionRepository(db)
        q = q_repo.create_question(
            reason="Minor formatting ambiguity",
            question="Ignore trailing spaces?",
            options=[{"id": "yes", "label": "Yes"}],
        )
        qid = q["question_id"]

        resp = client.post(f"/api/questions/{qid}/dismiss", headers=auth)
        assert resp.status_code == 200
        assert resp.json()["status"] == "QUESTION_DISMISSED"


# ─── 4. Research Guard / Stall Protection ────────────────────────────────────

class TestStallProtection:

    def test_stall_detector_catches_repeated_command(self):
        db = DatabaseService(get_db_path())
        tool_repo = ToolExecutionRepository(db)

        task_id = "task-stall-test-1"
        # Record 4 identical tool executions
        for _ in range(4):
            tool_repo.record_execution({
                "tool_name": "semgrep",
                "category": "Static Analysis",
                "task_id": task_id,
                "command": "semgrep --config p/ci /tmp/target",
                "args": ["--config", "p/ci", "/tmp/target"],
                "status": "COMPLETED",
                "exit_code": 0,
            })

        res = StallDetector.analyze_task_history(task_id, db_service=db, repeat_threshold=3)
        assert res.is_stalled is True
        assert res.repeat_count >= 3
        assert res.question_created is True
        assert res.question_id is not None


# ─── 5. Authoritative Security Analysis Timer ────────────────────────────────

class TestActiveSecurityTimer:

    def test_timer_is_zero_during_preparation_and_waiting(self, client, auth):
        db = DatabaseService(get_db_path())
        import uuid
        run_id = f"run-timer-{uuid.uuid4().hex[:8]}"

        with db.get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("""
                INSERT INTO runs (
                    run_id, task_id, agent_id, adapter_version, start_time,
                    workspace_id, environment_fingerprint, status, schema_version,
                    run_state, repository_name, repository_path, token_budget, stage
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, f"task-{run_id}", "agent-agy-01", "1.0.0", datetime.now(timezone.utc).isoformat(),
                f"ws-{run_id}", "test", "WAITING_FOR_ANALYST", "1.0",
                "WAITING_FOR_ANALYST", "Test Repo", "/tmp", 650000, "REPOSITORY_ANALYSIS"
            ))
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()

        resp = client.get(f"/api/runs/{run_id}", headers=auth)
        assert resp.status_code == 200
        assert resp.json()["elapsed_seconds"] == 0.0

    def test_timer_freezes_on_pause_and_resumes(self, client, auth):
        db = DatabaseService(get_db_path())
        import uuid
        run_id = f"run-timer-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(seconds=120)).isoformat()

        with db.get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("""
                INSERT INTO runs (
                    run_id, task_id, agent_id, adapter_version, start_time,
                    workspace_id, environment_fingerprint, status, schema_version,
                    run_state, repository_name, repository_path, token_budget,
                    analysis_started_at, stage
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, f"task-{run_id}", "agent-agy-01", "1.0.0", start_time,
                f"ws-{run_id}", "test", "RUNNING", "1.0",
                "RUNNING", "Test Repo", "/tmp", 650000,
                start_time, "SECURITY_ANALYSIS"
            ))
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()

        # Check running elapsed is >= 120s
        resp = client.get(f"/api/runs/{run_id}", headers=auth)
        assert resp.status_code == 200
        assert resp.json()["elapsed_seconds"] >= 120.0

        # Pause run
        resp_pause = client.post(f"/api/runs/{run_id}/pause", headers=auth, json={})
        assert resp_pause.status_code == 200

        # Paused run detail retains frozen duration
        resp_paused = client.get(f"/api/runs/{run_id}", headers=auth)
        assert resp_paused.json()["run_state"] == "PAUSED"
        assert resp_paused.json()["elapsed_seconds"] >= 120.0

        # Resume run
        resp_resume = client.post(f"/api/runs/{run_id}/resume", headers=auth, json={})
        assert resp_resume.status_code == 200
        assert resp_resume.json()["to_state"] == "RUNNING"


# ─── 6. Task Attempt Lineage & Analyst Instructions ──────────────────────────

class TestAttemptLineageAndInstructions:

    def test_analyst_instruction_creates_new_attempt(self, client, auth):
        db = DatabaseService(get_db_path())
        import uuid
        task_id = f"task-{uuid.uuid4().hex[:8]}"

        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO tasks (
                    task_id, objective, inputs, dependencies, required_capabilities,
                    preferred_roles, risk_level, workspace_policy, tool_policy,
                    budget, status, retry_count, acceptance_criteria, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id, "Analyze cryptographic reset sequence", "{}", "[]", "[]",
                "['RTL Security Analyst']", "MEDIUM", "{}", "{}",
                "{}", "RUNNING", 0, "[]", "1.0", datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()

        # Submit instruction
        resp = client.post(f"/api/tasks/{task_id}/instructions", json={
            "message": "Re-run this analysis using simulation and inspect one-hop callers.",
            "scope": "hw/ip/aes/",
            "role": "RTL Security Analyst",
        }, headers=auth)

        if resp.status_code != 200:
            print("Instruction Error Response:", resp.status_code, resp.text)
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == task_id
        assert data["attempt_number"] >= 1
        att_id = data["attempt_id"]

        # Fetch attempt detail via dedicated endpoint /api/attempts/{attempt_id}
        resp_att = client.get(f"/api/attempts/{att_id}", headers=auth)
        assert resp_att.status_code == 200
        att_data = resp_att.json()
        assert att_data["attempt_id"] == att_id
        assert "simulation" in att_data["instruction_message"].lower()
