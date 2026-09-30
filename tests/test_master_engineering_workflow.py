import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from history.database import DatabaseService
from history.project_repository import ProjectRepository
from history.project_logger import ProjectLogger
from orchestrator.orchestrator import CentralOrchestrator
from api.app import app

@pytest.fixture
def clean_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_workflow.db")
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

def test_project_manifest_endpoint(tmp_path, app_client):
    repo_dir = tmp_path / "mock_rust_target"
    repo_dir.mkdir()
    (repo_dir / "Cargo.toml").write_text('[package]\nname = "mock_rust"\nversion = "0.1.0"\n')
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "main.rs").write_text('fn main() { println!("test"); }\n')

    # Create project
    res = app_client.post("/api/projects", json={
        "project_name": "Manifest Test Project",
        "target_directory": str(repo_dir)
    })
    assert res.status_code == 200, res.text
    data = res.json()
    proj_id = data["project_id"]

    # Request manifest
    m_res = app_client.get(f"/api/projects/{proj_id}/manifest")
    assert m_res.status_code == 200, m_res.text
    manifest = m_res.json()
    assert manifest["project_id"] == proj_id
    assert "Rust" in manifest["languages"]
    assert manifest["build_system"] == "Cargo"


def test_project_briefing_seven_questions_and_intake_progress(tmp_path, app_client):
    repo_dir = tmp_path / "briefing_target"
    repo_dir.mkdir()
    (repo_dir / "Cargo.toml").write_text('[package]\nname = "briefing_test"\n')
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "lib.rs").write_text('pub fn calculate_privilege() -> u8 { 0 }\n')

    res = app_client.post("/api/projects", json={
        "project_name": "Briefing Test Project",
        "target_directory": str(repo_dir)
    })
    proj_id = res.json()["project_id"]

    b_res = app_client.get(f"/api/projects/{proj_id}/briefing")
    assert b_res.status_code == 200
    briefing = b_res.json()

    # Verify intake progress 5 stages
    intake_progress = briefing.get("intake_progress", {})
    assert intake_progress.get("percent") == 100
    assert intake_progress.get("status") == "COMPLETED"
    stages = intake_progress.get("stages", [])
    assert len(stages) == 5
    stage_names = [s["name"] for s in stages]
    assert "File inventory" in stage_names
    assert "Language detection" in stage_names
    assert "Build detection" in stage_names
    assert "Manifest parsing" in stage_names
    assert "Security surface extraction" in stage_names
    for s in stages:
        assert s["status"] == "COMPLETED"

    # Verify 7 core briefing answers
    assert "what_is_this" in briefing
    assert "what_did_i_find" in briefing
    assert "what_can_i_analyze" in briefing
    assert "what_dont_i_understand" in briefing
    assert "what_looks_important" in briefing
    assert "what_do_i_recommend" in briefing
    assert "what_would_cost" in briefing


def test_project_logger_and_logs_endpoint(clean_db, app_client):
    proj_repo = ProjectRepository(clean_db)
    proj = proj_repo.create_project(name="Log Test Proj", target_directory="/tmp/log_test")
    proj_id = proj["project_id"]

    # Log actions using ProjectLogger
    ProjectLogger.log_project(proj_id, "Project created successfully.")
    ProjectLogger.log_intake(proj_id, "Completed file inventory and language detection.")
    ProjectLogger.log_orchestrator(proj_id, "Dispatched workpackage WP-01.")
    ProjectLogger.log_realtime(proj_id, "CONNECTED", "Client subscribed to project events.")
    ProjectLogger.log_tool_execution(
        project_id=proj_id,
        run_id="run-01",
        tool_id="rust_source_inspector",
        command="ripgrep privilege",
        exit_code=0,
        duration_ms=45.2,
        stdout_snippet="Found 2 occurrences",
        task_id="task-123"
    )

    # Query log files
    summary = ProjectLogger.get_logs_summary(proj_id)
    assert summary["project_id"] == proj_id
    assert summary["logs"]["project.log"]["exists"] is True
    assert summary["logs"]["intake.log"]["exists"] is True
    assert summary["logs"]["orchestrator.log"]["exists"] is True
    assert summary["logs"]["realtime.log"]["exists"] is True

    # Verify via API
    res = app_client.get(f"/api/projects/{proj_id}/logs")
    assert res.status_code == 200
    api_summary = res.json()
    assert api_summary["project_id"] == proj_id
    assert api_summary["logs"]["project.log"]["exists"] is True


def test_human_friendly_project_local_identifiers(clean_db, app_client):
    proj_repo = ProjectRepository(clean_db)
    proj = proj_repo.create_project(name="IDs Test Proj", target_directory="/tmp/id_test")
    proj_id = proj["project_id"]

    now = datetime.now(timezone.utc).isoformat()
    f1_id = f"find-{uuid.uuid4().hex[:8]}"
    f2_id = f"find-{uuid.uuid4().hex[:8]}"
    with clean_db.get_connection() as conn:
        conn.execute(
            "INSERT INTO findings (finding_id, project_id, fingerprint, hypothesis, locations, "
            "supporting_evidence, contradicting_evidence, validation_method, validator_result, "
            "state, lineage, timestamps, schema_version, task_id, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f1_id, proj_id, "fp1", "Test hypothesis 1", "[]", "[]", "[]", None, None,
             "CONFIRMED", "{}", "{}", "1.0", None, "2026-09-29T10:00:00Z", "2026-09-29T10:00:00Z")
        )
        conn.execute(
            "INSERT INTO findings (finding_id, project_id, fingerprint, hypothesis, locations, "
            "supporting_evidence, contradicting_evidence, validation_method, validator_result, "
            "state, lineage, timestamps, schema_version, task_id, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f2_id, proj_id, "fp2", "Test hypothesis 2", "[]", "[]", "[]", None, None,
             "OPEN", "{}", "{}", "1.0", None, "2026-09-29T10:01:00Z", "2026-09-29T10:01:00Z")
        )

        # Insert evidence records
        e1_id = f"evi-{uuid.uuid4().hex[:8]}"
        e2_id = f"evi-{uuid.uuid4().hex[:8]}"
        conn.execute(
            "INSERT INTO evidence (evidence_id, project_id, task_id, run_id, agent_id, source_type, "
            "raw_hash, canonical_hash, semantic_fingerprint, environment_fingerprint, "
            "exit_status, provenance, schema_version, finding_id, source_tool, timestamp, "
            "semantic_identity) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (e1_id, proj_id, "task-t1", "run-r1", "agent-agy-01", "TOOL_OUTPUT",
             "abc123", "def456", "semfp1", "envfp", 0, "{}", "1.0",
             f1_id, "rust_source_inspector", "2026-09-29T10:00:00Z", "sem-id-1")
        )
        conn.execute(
            "INSERT INTO evidence (evidence_id, project_id, task_id, run_id, agent_id, source_type, "
            "raw_hash, canonical_hash, semantic_fingerprint, environment_fingerprint, "
            "exit_status, provenance, schema_version, finding_id, source_tool, timestamp, "
            "semantic_identity) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (e2_id, proj_id, "task-t1", "run-r1", "agent-agy-01", "TOOL_OUTPUT",
             "abc124", "def457", "semfp2", "envfp", 0, "{}", "1.0",
             f2_id, "cargo test", "2026-09-29T10:01:00Z", "sem-id-2")
        )
        conn.commit()

    # Query findings API
    res_f = app_client.get(f"/api/findings?project_id={proj_id}")
    assert res_f.status_code == 200
    findings = res_f.json()["items"]
    assert len(findings) == 2
    # Verify display IDs are assigned (e.g. PROJ-001-VUL-001 or VUL-001)
    assert "VUL-" in findings[0]["display_id"]
    assert "VUL-" in findings[1]["display_id"]

    # Query single finding
    res_f_single = app_client.get(f"/api/findings/{f1_id}")
    assert res_f_single.status_code == 200
    assert "VUL-" in res_f_single.json()["display_id"]

    # Query evidence API
    res_e = app_client.get(f"/api/evidence?project_id={proj_id}")
    assert res_e.status_code == 200
    evis = res_e.json()["items"]
    assert len(evis) == 2
    assert "EVI-" in evis[0]["display_id"]
    assert "EVI-" in evis[1]["display_id"]

    # Query single evidence
    res_e_single = app_client.get(f"/api/evidence/{e1_id}")
    assert res_e_single.status_code == 200
    assert "EVI-" in res_e_single.json()["display_id"]


def test_claude_execution_strictly_zero():
    orch = CentralOrchestrator()
    with pytest.raises(PermissionError, match="Execution Policy strictly blocks Claude execution"):
        orch.create_user_task(goal="Check Claude", target_files=[], agent_id="agent-claude-01")
