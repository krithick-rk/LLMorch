"""
Unit & Integration Tests - Phase 1 Single-Agent Workflow
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from repository_intelligence.intake import RepositoryIntake
from repository_intelligence.noise_filter import NoiseFilter, FileClassification
from tools.precheck import DeterministicPreChecker
from sandbox.workspace import WorkspaceManager
from validator.engine import FindingValidator
from adapters.agy_adapter import AGYAdapter
from orchestrator.investigation import InvestigationWorkflow
from history.database import DatabaseService


def test_repository_intake():
    with tempfile.TemporaryDirectory() as tmpdir:
        intake = RepositoryIntake(tmpdir)
        snapshot = intake.create_snapshot()
        assert snapshot.absolute_root == str(Path(tmpdir).resolve())
        assert snapshot.repository_type in ("git", "directory")


def test_noise_filter():
    files = [
        "src/main.py",
        "build/output.o",
        "node_modules/lib.js",
        ".git/config",
        "docs/readme.md"
    ]
    filtered = NoiseFilter.filter_paths_for_llm(files)
    assert "src/main.py" in filtered
    assert "build/output.o" not in filtered
    assert ".git/config" not in filtered


def test_deterministic_precheck():
    with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False) as tmp:
        tmp.write("def foo():\n    eval('1+1')\n")
        tmp_path = tmp.name

    try:
        res = DeterministicPreChecker.run_prechecks([tmp_path])
        assert res.passed is True
        assert len(res.findings) > 0
        assert "eval()" in res.findings[0]["description"]
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_workspace_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        wm = WorkspaceManager(base_workspaces_dir=tmpdir)
        ws = wm.create_workspace(repo_root=str(PROJECT_ROOT), workflow_id="wf-test", task_id="task-test")
        assert os.path.exists(ws.working_directory)
        wm.cleanup_workspace(ws)
        assert not os.path.exists(ws.working_directory)


def test_citation_validator():
    locations = [{"file_path": "pyproject.toml", "start_line": 1}]
    res = FindingValidator.validate_reference_locations(locations, str(PROJECT_ROOT))
    assert res["status"] == "VALID_REFERENCE"
    assert res["valid_count"] == 1


def test_investigation_workflow_end_to_end_mock_cli():
    db = DatabaseService(":memory:")
    workflow = InvestigationWorkflow(
        repo_path=str(PROJECT_ROOT),
        target_component="schemas",
        db_service=db
    )
    result = workflow.run()
    assert result["workflow_id"].startswith("wf-")
    assert result["task_status"] in ("SUCCEEDED", "FAILED")
    assert result["assigned_agent"] == "agent-agy-01"
    assert result["finding_id"].startswith("find-")


if __name__ == "__main__":
    pytest.main([__file__])
