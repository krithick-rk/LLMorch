"""
tests/test_project_isolation.py

Verifies strict project isolation, project-scoped runtime, and Burp Suite-style project model:
1. Fundamental Project Rule: 1 Project = 1 Target Repository/Directory
2. Clean Start: Newly created project has 0 tasks, 0 decisions, 0 runs, 0 evidence, 0 findings, idle timer
3. Data Isolation: Project A data NEVER leaks into Project B
4. Switching: Switching A -> B -> A restores exact respective state
5. Archival: Archived projects are hidden from active listing and summary
6. API Scoping: Queries enforce project_id server-side
"""

import pytest
import tempfile
import os
import shutil
from fastapi.testclient import TestClient

from history.database import DatabaseService
from history.project_repository import ProjectRepository
from api.app import app


@pytest.fixture
def clean_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_isolation.db")
    db = DatabaseService(db_path=db_path)
    yield db
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def app_client(clean_db, monkeypatch):
    monkeypatch.setattr("api.routers.projects._get_project_repo", lambda: ProjectRepository(clean_db))
    monkeypatch.setattr("api.routers.tasks._get_db", lambda: clean_db)
    monkeypatch.setattr("api.routers.questions._get_db", lambda: clean_db)
    monkeypatch.setattr("api.routers.runs._get_db", lambda: clean_db)
    monkeypatch.setattr("api.routers.findings._get_db", lambda: clean_db)
    monkeypatch.setattr("api.routers.evidence._get_db", lambda: clean_db)
    monkeypatch.setattr("api.routers.supervisor._get_db", lambda: clean_db)
    monkeypatch.setattr("api.routers.closure._get_db", lambda: clean_db)
    monkeypatch.setattr("api.routers.repository._get_db", lambda: clean_db)

    client = TestClient(app)
    return client


def test_project_model_one_repo_rule(clean_db):
    """Rule 1: One Project = One Target Repository/Directory."""
    proj_repo = ProjectRepository(clean_db)
    
    p1 = proj_repo.create_project(
        name="Project Alpha",
        target_directory="/tmp/repo_alpha",
        status="ACTIVE"
    )
    
    loaded = proj_repo.get_project(p1["project_id"])
    assert loaded is not None
    assert loaded["target_directory"] == "/tmp/repo_alpha"
    assert loaded["project_id"] == p1["project_id"]


def test_new_project_starts_clean(clean_db, app_client):
    """Rule 2 & 20: Newly created project starts with 0 project-local history."""
    # Create Project 001
    res1 = app_client.post("/api/projects", json={
        "project_name": "Untitled Project 001",
        "target_directory": "/tmp/test1"
    })
    assert res1.status_code == 200
    p1_id = res1.json()["project_id"]

    # Add a task to Project 001
    app_client.post("/api/tasks", json={
        "task_id": "task-alpha-01",
        "title": "Alpha Clock Verification",
        "project_id": p1_id,
        "bucket": "RESET_AND_CLOCK"
    })

    # Add a question to Project 001
    q_res1 = app_client.post("/api/questions", json={
        "project_id": p1_id,
        "reason": "Alpha Reset Topology Question",
        "question": "Is async reset synchronized?",
        "options": [
            {"id": "yes", "label": "Yes", "description": "Synchronized"},
            {"id": "no", "label": "No", "description": "Not synchronized"}
        ],
        "default_option": "yes"
    })
    assert q_res1.status_code == 200

    # Now create Project 002
    res2 = app_client.post("/api/projects", json={
        "project_name": "Untitled Project 002",
        "target_directory": "/tmp/test2"
    })
    assert res2.status_code == 200
    p2_id = res2.json()["project_id"]

    # Check Project 002 summary
    summary_res = app_client.get(f"/api/projects/{p2_id}/summary")
    assert summary_res.status_code == 200
    s2 = summary_res.json()

    assert s2["tasks"] == 0
    assert s2["decisions"] == 0
    assert s2["open_decisions"] == 0
    assert s2["findings"] == 0
    assert s2["evidence"] == 0
    assert s2["runs"] == 0
    assert s2["verification_plans"] == 0
    assert s2["runtime_state"] == "IDLE"
    assert s2["elapsed_seconds"] == 0


def test_project_switch_isolation(clean_db, app_client):
    """Rule 24: Switch Project A -> Project B -> Project A."""
    # Create Project A
    res_a = app_client.post("/api/projects", json={
        "project_name": "Project A",
        "target_directory": "/tmp/repo_A"
    })
    p_a = res_a.json()["project_id"]

    # Create Task A1, Question A1, Evidence A1 in Project A
    app_client.post("/api/tasks", json={
        "task_id": "task-A1",
        "title": "Task A1",
        "project_id": p_a,
        "bucket": "ACCESS_CONTROL"
    })
    q_res_a = app_client.post("/api/questions", json={
        "project_id": p_a,
        "reason": "Decision A1",
        "question": "Authorize privilege escalation?",
        "options": [
            {"id": "deny", "label": "Deny", "description": "Deny privilege escalation"},
            {"id": "allow", "label": "Allow", "description": "Allow escalation"}
        ],
        "default_option": "deny"
    })
    assert q_res_a.status_code == 200
    with clean_db.get_connection() as conn:
        conn.execute("""
            INSERT INTO evidence (evidence_id, project_id, agent_id, source_type, raw_hash, canonical_hash,
                                  semantic_fingerprint, environment_fingerprint, exit_status, provenance,
                                  schema_version, semantic_identity, source_tool, task_id, run_id, timestamp)
            VALUES ('ev-A1', ?, 'agent-agy-01', 'TOOL_OUTPUT', 'h1', 'ch1', 'sfp1', 'efp1', 0, '{}', '1.0', 'sid1', 'Yosys', 'task-A1', 'run-A1', '2026-09-28T00:00:00Z')
        """, (p_a,))
        conn.commit()

    # Create Project B
    res_b = app_client.post("/api/projects", json={
        "project_name": "Project B",
        "target_directory": "/tmp/repo_B"
    })
    p_b = res_b.json()["project_id"]

    # Activate Project B
    app_client.post(f"/api/projects/{p_b}/activate")

    # Verify Project B sees 0 tasks, 0 decisions, 0 evidence
    tasks_b = app_client.get(f"/api/tasks?project_id={p_b}").json()
    assert tasks_b["total"] == 0
    assert len(tasks_b["items"]) == 0

    decisions_b = app_client.get(f"/api/questions?project_id={p_b}").json()
    assert decisions_b["total"] == 0

    evidence_b = app_client.get(f"/api/evidence?project_id={p_b}").json()
    assert evidence_b["total"] == 0

    # Create Task B1 in Project B
    app_client.post("/api/tasks", json={
        "task_id": "task-B1",
        "title": "Task B1",
        "project_id": p_b,
        "bucket": "CRYPTO_ACCELERATOR"
    })

    # Switch back to Project A
    app_client.post(f"/api/projects/{p_a}/activate")

    # Verify Project A has Task A1, Decision A1, Evidence A1, but NOT Task B1
    tasks_a = app_client.get(f"/api/tasks?project_id={p_a}").json()
    assert tasks_a["total"] == 1
    assert tasks_a["items"][0]["task_id"] == "task-A1"

    decisions_a = app_client.get(f"/api/questions?project_id={p_a}").json()
    assert decisions_a["total"] == 1
    assert decisions_a["items"][0]["reason"] == "Decision A1"

    evidence_a = app_client.get(f"/api/evidence?project_id={p_a}").json()
    assert evidence_a["total"] == 1
    assert evidence_a["items"][0]["evidence_id"] == "ev-A1"

    # Switch to Project B again
    app_client.post(f"/api/projects/{p_b}/activate")
    tasks_b_revisit = app_client.get(f"/api/tasks?project_id={p_b}").json()
    assert tasks_b_revisit["total"] == 1
    assert tasks_b_revisit["items"][0]["task_id"] == "task-B1"


def test_project_archive_behavior(clean_db, app_client):
    """Rule 27: Archived projects must not appear in active listings."""
    res = app_client.post("/api/projects", json={
        "project_name": "Project to Archive",
        "target_directory": "/tmp/to_archive"
    })
    p_id = res.json()["project_id"]

    # Archive the project
    arch_res = app_client.post(f"/api/projects/{p_id}/archive")
    assert arch_res.status_code == 200

    # Default list_projects must not contain it
    list_res = app_client.get("/api/projects").json()
    active_ids = [p["project_id"] for p in list_res["projects"]]
    assert p_id not in active_ids
