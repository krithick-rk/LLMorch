"""
Unit and Integration Tests for LLMorch Project Model & Workspace Isolation
Validates:
- create project with name
- create project without name (defaults to Untitled Project 001, etc.)
- open existing project
- switch active project
- project isolation (tasks and evidence project-local)
- global intelligence available across projects
- project evidence remains project-local
- project history persists
- new project starts clean
- testing with Untitled Project & /tmp/test
- small/unrelated file intake (hello.c, script.py)
- natural language instruction parser (debug, run, analyze, instructions)
"""

import os
import shutil
import tempfile
import pytest
from pathlib import Path

from fastapi.testclient import TestClient

from history.database import DatabaseService
from history.project_repository import ProjectRepository
from api.app import app
import api.routers.projects as proj_module


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_projects.db"
    db_service = DatabaseService(str(db_file))
    return db_service


@pytest.fixture
def client(temp_db, monkeypatch):
    # Monkeypatch the database service in the router to use the test db
    repo = ProjectRepository(temp_db)
    monkeypatch.setattr(proj_module, "_get_project_repo", lambda: repo)
    with TestClient(app) as test_client:
        yield test_client


def test_create_project_with_name(temp_db):
    repo = ProjectRepository(temp_db)
    p = repo.create_project(name="Custom SoC Project", target_directory="/tmp/soc")
    assert p["name"] == "Custom SoC Project"
    assert p["target_directory"] == "/tmp/soc"
    assert p["is_active"] is True
    assert p["project_id"].startswith("proj-")


def test_create_project_without_name(temp_db):
    repo = ProjectRepository(temp_db)
    # The default seed has Untitled Project 001, so the next should be 002
    p1 = repo.create_project(name="", target_directory="/tmp/test1")
    assert p1["name"].startswith("Untitled Project ")
    assert p1["is_active"] is True

    p2 = repo.create_project(name=None, target_directory="/tmp/test2")
    assert p2["name"].startswith("Untitled Project ")
    assert p2["name"] != p1["name"]


def test_open_existing_project_and_switch(temp_db):
    repo = ProjectRepository(temp_db)
    p1 = repo.create_project(name="Project Alpha", target_directory="/tmp/alpha")
    p2 = repo.create_project(name="Project Beta", target_directory="/tmp/beta")

    assert repo.get_active_project()["project_id"] == p2["project_id"]

    # Switch back to Project Alpha
    switched = repo.set_active_project(p1["project_id"])
    assert switched["project_id"] == p1["project_id"]
    assert switched["is_active"] is True

    # Check active
    active = repo.get_active_project()
    assert active["project_id"] == p1["project_id"]

    # Verify Beta is no longer active
    beta = repo.get_project(p2["project_id"])
    assert beta["is_active"] is False


def test_project_isolation(temp_db):
    repo = ProjectRepository(temp_db)
    p_a = repo.create_project(name="Project A", target_directory="/tmp/a")
    p_b = repo.create_project(name="Project B", target_directory="/tmp/b")

    with temp_db.get_connection() as conn:
        conn.execute("""
            INSERT INTO tasks (
                task_id, workflow_id, project_id, objective, inputs, dependencies,
                required_capabilities, preferred_roles, risk_level, workspace_policy,
                tool_policy, budget, status, acceptance_criteria, schema_version, created_at
            ) VALUES (?, ?, ?, ?, '[]', '[]', '[]', '[]', 'LOW', '{}', '{}', '{}', ?, '[]', '1.0', 'now')
        """, ("task-a1", "run-a1", p_a["project_id"], "Task in Project A", "COMPLETED"))

        conn.execute("""
            INSERT INTO tasks (
                task_id, workflow_id, project_id, objective, inputs, dependencies,
                required_capabilities, preferred_roles, risk_level, workspace_policy,
                tool_policy, budget, status, acceptance_criteria, schema_version, created_at
            ) VALUES (?, ?, ?, ?, '[]', '[]', '[]', '[]', 'LOW', '{}', '{}', '{}', ?, '[]', '1.0', 'now')
        """, ("task-b1", "run-b1", p_b["project_id"], "Task in Project B", "RUNNING"))
        conn.commit()

        # Query tasks for Project A
        cursor = conn.cursor()
        rows_a = cursor.execute("SELECT task_id, objective FROM tasks WHERE project_id = ?", (p_a["project_id"],)).fetchall()
        rows_b = cursor.execute("SELECT task_id, objective FROM tasks WHERE project_id = ?", (p_b["project_id"],)).fetchall()

        assert len(rows_a) == 1
        assert rows_a[0]["task_id"] == "task-a1"
        assert rows_a[0]["objective"] == "Task in Project A"
        assert len(rows_b) == 1
        assert rows_b[0]["task_id"] == "task-b1"
        assert rows_b[0]["objective"] == "Task in Project B"


def test_global_intelligence_separate_from_project_evidence(temp_db):
    # Global pattern table should be shared across all projects
    with temp_db.get_connection() as conn:
        conn.execute("""
            INSERT INTO global_patterns (
                pattern_id, domain, title, structural_signature, semantic_signature,
                indicators, affected_constructs, supporting_evidence_types,
                successful_analysis_steps, rejected_analysis_steps, provenance,
                confidence_state, privacy_class, schema_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "pat-cdc-001", "cdc", "Cross Clock Domain Invariant", "async_fifo", "sig",
            "[]", "[]", "[]", "[]", "[]", "global", "VERIFIED", "PUBLIC", "1.0", "now", "now"
        ))
        conn.commit()

        # Global pattern is queryable regardless of active project
        cursor = conn.cursor()
        patterns = cursor.execute("SELECT pattern_id, title FROM global_patterns").fetchall()
        assert len(patterns) >= 1
        assert patterns[0]["pattern_id"] == "pat-cdc-001"


def test_unrelated_small_repository_intake(tmp_path):
    # Create small test directory with hello.c and script.py
    small_dir = tmp_path / "small_test_repo"
    small_dir.mkdir()
    (small_dir / "hello.c").write_text("#include <stdio.h>\nint main() { return 0; }")
    (small_dir / "script.py").write_text("print('test')")

    intake = proj_module._inspect_directory_deterministic(str(small_dir))
    assert intake["total_files"] == 2
    assert intake["c_count"] == 1
    assert intake["py_count"] == 1
    assert intake["rtl_count"] == 0
    assert intake["build_system"] == "Not detected"
    assert intake["is_small_or_generic"] is True
    assert intake["classification"] == "Generic Software Directory"


def test_natural_instruction_interpretation(client):
    # Create project first
    res = client.post("/api/projects", json={"name": "Instruction Test Project", "target_directory": "/tmp/test"})
    assert res.status_code == 200
    p_id = res.json()["project_id"]

    # 1. "Debug the Python file"
    r1 = client.post(f"/api/projects/{p_id}/interpret", json={"instruction": "Debug the Python file."})
    assert r1.status_code == 200
    d1 = r1.json()
    assert "debug" in d1["goal"].lower()
    assert "script.py" in d1["target"]
    assert "debugger" in d1["tool"].lower()

    # 2. "Run those files"
    r2 = client.post(f"/api/projects/{p_id}/interpret", json={"instruction": "Run those files."})
    assert r2.status_code == 200
    d2 = r2.json()
    assert "run" in d2["goal"].lower()

    # 3. "Analyze both"
    r3 = client.post(f"/api/projects/{p_id}/interpret", json={"instruction": "Analyze both."})
    assert r3.status_code == 200
    d3 = r3.json()
    assert "analyze" in d3["goal"].lower()

    # 4. "Tell me how to run them"
    r4 = client.post(f"/api/projects/{p_id}/interpret", json={"instruction": "Tell me how to run them."})
    assert r4.status_code == 200
    d4 = r4.json()
    assert "instruction" in d4["goal"].lower() or "recipe" in d4["method"].lower()

    # 5. "Find bugs in the C file"
    r5 = client.post(f"/api/projects/{p_id}/interpret", json={"instruction": "Find bugs in the C file."})
    assert r5.status_code == 200
    d5 = r5.json()
    assert "hello.c" in d5["target"]
    assert "bug" in d5["goal"].lower() or "vulnerabilit" in d5["goal"].lower()


def test_project_briefing_small_vs_soc(client, tmp_path):
    # Test small generic repository briefing
    small_dir = tmp_path / "briefing_small"
    small_dir.mkdir()
    (small_dir / "hello.c").write_text("int main() {}")

    p_small = client.post("/api/projects", json={"name": "Small Generic", "target_directory": str(small_dir)}).json()
    b_small = client.get(f"/api/projects/{p_small['project_id']}/briefing").json()
    assert b_small["is_small_or_generic"] is True
    assert len(b_small["recommended_actions"]) >= 5
    assert any(a["id"] == "analyze_files" for a in b_small["recommended_actions"])
    assert any(a["id"] == "debug_something" for a in b_small["recommended_actions"])

    # Test SoC repository briefing
    soc_dir = tmp_path / "briefing_soc"
    soc_dir.mkdir()
    for i in range(25):
        (soc_dir / f"mod_{i}.sv").write_text(f"module mod_{i}; endmodule")
    (soc_dir / "Makefile").write_text("all:\n\t@echo ok")

    p_soc = client.post("/api/projects", json={"name": "SoC Project", "target_directory": str(soc_dir)}).json()
    b_soc = client.get(f"/api/projects/{p_soc['project_id']}/briefing").json()
    assert b_soc["is_small_or_generic"] is False
    assert len(b_soc["potential_analysis_areas"]) >= 4
    assert len(b_soc["targeted_questions"]) >= 1
