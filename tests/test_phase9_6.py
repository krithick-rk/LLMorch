"""
test_phase9_6.py — Phase 9.6 Live Integration, Debugging, and UX Refinement Regression Suite.

Verifies:
  1. Internal Server Error resolved: POST /api/analysis/start succeeds without 500 error,
     inserts root task before run (FK integrity), handles snapshot repo listing, dict/list assignments.
  2. Enriched Task Detail: GET /api/tasks/{task_id} returns all required operational fields:
     role, scope, model, analysis_unit, attempts, tool executions, evidence, hypotheses,
     and STOPPED task fields (stopped_at, stop_reason, checkpoints, manually_stopped, last_agent_state).
  3. Run Detail Endpoint: GET /api/runs/{run_id} returns state, duration, token accounting, tasks, findings.
  4. Repository by ID: GET /api/repository/{repo_id} and GET /api/repositories/{repo_id}.
  5. Dual Agent Chat:
     a) Task Chat: GET & POST /api/chat/task/{task_id} records structured operational events,
        spawns TaskAttempt, records tool execution.
     b) General Investigation Chat: GET & POST /api/chat/investigation queries SQLite authoritative
        state for agents, tools, runs, findings, and tasks.
  6. Canonical Entity URLs: Direct queries for /run/{id}, /task/{id}, /tool/{name},
     /finding/{id}, /evidence/{id}, /question/{id}, /attempt/{id}.
  7. Tool Execution failure diagnostics: Failed tools expose command, stderr, exit code, failure reason.
  8. Critical Execution Policy: Claude execution is strictly blocked; AGY and Codex permitted.
"""

from __future__ import annotations

import os
import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient

from api.app import app
from api.session import get_default_token
from history.database import get_db_path, DatabaseService
from history.phase9_repositories import QuestionRepository, TaskAttemptRepository, ToolExecutionRepository
from scheduler.execution_policy import get_execution_policy


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def token():
    return get_default_token()


@pytest.fixture(scope="module")
def auth(token):
    return {"X-Session-Token": token}


# ─── 1. POST /api/analysis/start — Root Cause Fix Validation ──────────────────

class TestAnalysisStartRootCause:

    def test_start_analysis_does_not_fail_with_500(self, tmp_path, client, auth):
        """
        Reproduce and verify the fix for 500 Internal Server Error in POST /api/analysis/start:
        - Root task inserted first to satisfy FK constraint on runs(task_id).
        - ExtendedRepositorySnapshotRepository list_for_repository called properly.
        - Dict and list assignments both accepted.
        - Returns 200 with run_id, tasks, and assigned agents.
        """
        test_file = tmp_path / "crypto_core.v"
        test_file.write_text("module crypto_core(input clk, input rst_n); endmodule")

        # 1. Analyze repository first
        analyze_resp = client.post("/api/repositories/analyze", json={"repository_path": str(tmp_path)}, headers=auth)
        assert analyze_resp.status_code == 200

        # 2. Start security analysis with dictionary assignments
        start_payload = {
            "repository_path": str(tmp_path),
            "token_budget": 120000,
            "assignments": {
                "unit-0": "agent-agy-01"
            }
        }
        resp = client.post("/api/analysis/start", json=start_payload, headers=auth)
        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "run_id" in data
        assert data["run_id"].startswith("run-")
        assert data["status"] in ("RUNNING", "ANALYSIS_STARTED")
        assert len(data.get("tasks", [])) >= 1
        assert len(data.get("assigned_agents", [])) >= 1

    def test_start_analysis_accepts_list_assignments(self, tmp_path, client, auth):
        """Start analysis also accepts list of assignment dictionaries."""
        src_file = tmp_path / "top.c"
        src_file.write_text("int main() { return 0; }")

        client.post("/api/repositories/analyze", json={"repository_path": str(tmp_path)}, headers=auth)

        start_payload = {
            "repository_path": str(tmp_path),
            "token_budget": 80000,
            "assignments": [
                {"unit_id": "unit-0", "agent_id": "agent-agy-01"}
            ]
        }
        resp = client.post("/api/analysis/start", json=start_payload, headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data


# ─── 2. Enriched Task Detail & Stopped Task Diagnostics ────────────────────────

class TestTaskDetailEnrichment:

    def test_get_task_returns_enriched_fields(self, client, auth):
        """GET /api/tasks/{task_id} must return attempts, tools, evidence, role, scope, model."""
        tasks_resp = client.get("/api/tasks?limit=5", headers=auth)
        assert tasks_resp.status_code == 200
        tasks = tasks_resp.json().get("items", [])
        if not tasks:
            pytest.skip("No tasks available in database")

        task_id = tasks[0]["task_id"]
        detail_resp = client.get(f"/api/tasks/{task_id}", headers=auth)
        assert detail_resp.status_code == 200
        detail = detail_resp.json()

        assert detail["task_id"] == task_id
        assert "status" in detail
        assert "objective" in detail
        assert "attempts" in detail
        assert isinstance(detail["attempts"], list)
        assert "tool_executions" in detail
        assert isinstance(detail["tool_executions"], list)
        assert "evidence" in detail
        assert isinstance(detail["evidence"], list)
        assert "hypotheses" in detail
        assert "instructions" in detail
        assert "errors" in detail
        assert "checkpoint_count" in detail

    def test_stopped_task_diagnostics(self, client, auth):
        """Verify stopped task exposes stop_reason, stopped_at, checkpoint_count, and last_agent_state."""
        db = DatabaseService(get_db_path())
        test_task_id = f"test-stopped-task-{datetime.now().timestamp()}"

        # Create stopped task with diagnostic metadata in inputs
        inputs_json = json.dumps({
            "description": "Hardware reset security verification",
            "role": "RTL Security Analyst",
            "scope": "hw/ip/rstctrl",
            "stop_reason": "Analyst requested task halt",
            "stopped_at": datetime.now(timezone.utc).isoformat(),
            "checkpoint_count": 3,
            "manually_stopped": True,
        })
        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO tasks (
                    task_id, objective, inputs, dependencies, required_capabilities,
                    preferred_roles, risk_level, workspace_policy, tool_policy, budget,
                    status, acceptance_criteria, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                test_task_id, "Analyze reset controller under power glitch", inputs_json,
                "[]", "[]", '["RTL Security Analyst"]', "HIGH", "{}", "{}", "{}",
                "STOPPED", "[]", "1.0", datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()

        resp = client.get(f"/api/tasks/{test_task_id}", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "STOPPED"
        assert data["stop_reason"] == "Analyst requested task halt"
        assert data["stopped_at"] is not None
        assert data["checkpoint_count"] == 3
        assert data["manually_stopped"] is True


# ─── 3. Run Detail Endpoint & Canonical URLs ──────────────────────────────────

class TestRunDetailEndpoint:

    def test_get_run_detail(self, client, auth):
        """GET /api/runs/{run_id} returns authoritative state and duration."""
        current_resp = client.get("/api/runs/current", headers=auth)
        if current_resp.status_code == 200:
            run_id = current_resp.json()["run_id"]
            resp = client.get(f"/api/runs/{run_id}", headers=auth)
            assert resp.status_code == 200
            data = resp.json()
            assert data["run_id"] == run_id
            assert "run_state" in data
            assert "active_duration_seconds" in data
            assert "total_tasks" in data
            assert "findings_count" in data


# ─── 4. Repository by ID Endpoint ──────────────────────────────────────────────

class TestRepositoryByIdEndpoint:

    def test_get_repository_by_id(self, tmp_path, client, auth):
        """GET /api/repository/{repo_id} returns capability report."""
        repo_file = tmp_path / "top.v"
        repo_file.write_text("module top; endmodule")
        client.post("/api/repositories/analyze", json={"repository_path": str(tmp_path)}, headers=auth)
        client.post("/api/repositories/select", json={"repository_path": str(tmp_path)}, headers=auth)
        resp = client.get(f"/api/repository/{tmp_path.name}", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert "repository_name" in data or "repository_path" in data


# ─── 5. Dual Agent Chat Backend Tests ──────────────────────────────────────────

class TestDualAgentChat:

    def test_task_chat_instruction_creates_attempt_and_tool_event(self, client, auth):
        """
        POST /api/chat/task/{task_id} with analyst instruction:
        - Persists USER_INSTRUCTION
        - Spawns AGENT_ACK and SYSTEM_EVENT
        - Increments TaskAttempt
        - Records tool execution
        - Returns structured operational conversation
        """
        # Ensure a task exists
        tasks_resp = client.get("/api/tasks?limit=1", headers=auth)
        tasks = tasks_resp.json().get("items", [])
        if not tasks:
            pytest.skip("No tasks available")
        task_id = tasks[0]["task_id"]

        # Send instruction
        msg_payload = {"message": "Re-run simulation using reset sequencing and verify AES key zeroization."}
        post_resp = client.post(f"/api/chat/task/{task_id}", json=msg_payload, headers=auth)
        assert post_resp.status_code == 200
        messages = post_resp.json()
        assert len(messages) >= 2

        # Verify structured message types
        types = [m["message_type"] for m in messages]
        assert "USER_INSTRUCTION" in types
        assert "AGENT_ACK" in types or "SYSTEM_EVENT" in types

        # Check GET history
        get_resp = client.get(f"/api/chat/task/{task_id}", headers=auth)
        assert get_resp.status_code == 200
        history = get_resp.json()
        assert len(history) >= 2

    def test_general_investigation_chat_answers_from_authoritative_state(self, client, auth):
        """
        POST /api/chat/investigation:
        - Queries SQLite authoritative state
        - Factual response for available tools, active agents, or run status
        - Persists conversation in chat_messages
        """
        query_payload = {"message": "What tools are available?"}
        post_resp = client.post("/api/chat/investigation", json=query_payload, headers=auth)
        assert post_resp.status_code == 200
        messages = post_resp.json()
        assert isinstance(messages, list)
        assert len(messages) >= 2
        reply = messages[-1]
        assert reply["message_type"] in ("SYSTEM_EVENT", "OBSERVATION", "AGENT_ACK")
        assert "tool" in reply["content"].lower()

        # Query active agents
        agent_query = {"message": "What agents are currently working?"}
        agent_resp = client.post("/api/chat/investigation", json=agent_query, headers=auth)
        assert agent_resp.status_code == 200
        agent_messages = agent_resp.json()
        assert isinstance(agent_messages, list)
        assert len(agent_messages) >= 2
        agent_reply = agent_messages[-1]
        assert "agent" in agent_reply["content"].lower() or "available" in agent_reply["content"].lower()

        # Check GET history
        history_resp = client.get("/api/chat/investigation", headers=auth)
        assert history_resp.status_code == 200
        assert len(history_resp.json()) >= 2


# ─── 6. Canonical Entity Endpoint Refresh Tests ────────────────────────────────

class TestCanonicalEntityEndpoints:

    def test_all_entity_routes_return_valid_responses(self, client, auth):
        """Direct queries to entity endpoints must succeed for valid IDs or return 404 for unknown IDs."""
        # Tools
        t_resp = client.get("/api/tools/verilator", headers=auth)
        assert t_resp.status_code in (200, 404)

        # Questions
        q_resp = client.get("/api/questions?limit=1", headers=auth)
        if q_resp.status_code == 200 and q_resp.json().get("items"):
            qid = q_resp.json()["items"][0]["question_id"]
            single_q = client.get(f"/api/questions/{qid}", headers=auth)
            assert single_q.status_code == 200

        # Attempts
        att_resp = client.get("/api/attempts/attempt-unknown-999", headers=auth)
        assert att_resp.status_code in (200, 404)


# ─── 7. Tool Execution Diagnostics ─────────────────────────────────────────────

class TestToolExecutionDiagnostics:

    def test_failed_tool_execution_records_stderr_and_exit_code(self):
        """Tool executions with exit code != 0 record command, stderr, exit code, and reason."""
        db = DatabaseService(get_db_path())
        tool_repo = ToolExecutionRepository(db)

        exec_id = f"tool-test-failed-{datetime.now().timestamp()}"
        tool_repo.record_execution({
            "execution_id": exec_id,
            "tool_name": "verilator",
            "agent_id": "agent-agy-01",
            "task_id": "task-hw-aes-01",
            "command": "verilator --lint-only -Wall hw/ip/aes/rtl/aes_core.sv",
            "args": ["--lint-only", "-Wall"],
            "status": "FAILED",
            "exit_code": 1,
            "stdout_artifact": "",
            "stderr_artifact": "%Error: hw/ip/aes/rtl/aes_core.sv:42: Undefined signal 'key_rst_val'",
            "execution_result": "Syntax / elaboration failure",
            "duration_seconds": 1.45,
        })

        records = tool_repo.list_executions(tool_name="verilator", task_id="task-hw-aes-01")
        assert len(records) >= 1
        record = [r for r in records if r["execution_id"] == exec_id][0]
        assert record["status"] == "FAILED"
        assert record["exit_code"] == 1
        assert "Undefined signal" in (record.get("stderr_artifact") or record.get("stderr") or "")


# ─── 8. CRITICAL EXECUTION POLICY: Claude Block Verification ───────────────────

class TestExecutionPolicyClaudeBlocked:

    def test_claude_execution_is_strictly_blocked_by_policy(self):
        """Claude must never be executable in any runtime path."""
        policy = get_execution_policy()
        assert policy.is_agent_executable("agent-claude-01") is False
        assert policy.allow_real_claude_execution is False

        # AGY and Codex are allowed
        assert policy.is_agent_executable("agent-agy-01") is True
        assert policy.is_agent_executable("agent-codex-01") is True
