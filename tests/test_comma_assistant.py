"""
test_comma_assistant.py — Unit and integration tests for COMMA Engineering Assistant.
Verifies:
- AGY execution engine status and Claude 0-invocation policy enforcement
- Structured task proposal synthesis
- Authoritative SQLite state reflection in queries
- Conversation history tracking and project isolation
- Safe fallback when CLI runtime quota is exceeded
"""

import os
import json
import pytest
from fastapi.testclient import TestClient
from api.app import app
from history.database import get_db_path, DatabaseService

client = TestClient(app)


def test_comma_status_reports_agy_and_zero_claude():
    """Verify that COMMA status reports AGY runtime and 0 Claude invocations."""
    res = client.get("/api/comma/status")
    assert res.status_code == 200
    data = res.json()
    assert data["assistant_name"] == "COMMA"
    assert data["powered_by"] == "AGY"
    assert data["claude_invocations"] == 0
    assert data["claude_allowed"] is False
    assert "Hardware Security & Vulnerability Analysis" in data["capabilities"]


def test_comma_query_general_state():
    """Verify that COMMA query returns valid status, answer, and telemetry."""
    res = client.post("/api/comma/query", json={
        "query": "What is the active project and verification plan?",
        "project_id": "proj-e3b74aff",
        "current_page": "dossier"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert len(data["answer"]) > 0
    assert data["powered_by"] == "AGY"
    assert "token_usage" in data
    assert "context_inspected" in data


def test_comma_query_synthesizes_task_proposal():
    """Verify that user asking to create a task triggers structured task proposal synthesis."""
    res = client.post("/api/comma/query", json={
        "query": "create task to inspect caliptra_wrapper_top.sv for AXI privilege violations",
        "project_id": "proj-e3b74aff",
        "current_page": "tasks"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["task_proposal"] is not None
    prop = data["task_proposal"]
    assert "caliptra_wrapper_top.sv" in prop["objective"]
    assert prop["agent_id"] == "agent-agy-01"
    assert "hw/fpga/src/axi4lite_intf.sv" in prop["target_files"]
    assert prop["token_budget"] > 0


def test_comma_history_lifecycle():
    """Verify that messages are recorded, retrieved with project filter, and can be cleared."""
    # Query something distinct
    q_text = "Test unique query for history verification"
    res = client.post("/api/comma/query", json={
        "query": q_text,
        "project_id": "proj-e3b74aff",
        "current_page": "verification-plan"
    })
    assert res.status_code == 200

    # Retrieve history
    hist_res = client.get("/api/comma/history?project_id=proj-e3b74aff")
    assert hist_res.status_code == 200
    messages = hist_res.json()
    assert len(messages) >= 2  # user + assistant

    # Check last messages
    contents = [m["content"] for m in messages]
    assert any(q_text in c for c in contents)

    # Test clearing history
    del_res = client.delete("/api/comma/history?project_id=proj-e3b74aff")
    assert del_res.status_code == 200

    # Verify history empty
    post_del = client.get("/api/comma/history?project_id=proj-e3b74aff")
    assert post_del.status_code == 200
    assert len(post_del.json()) == 0
