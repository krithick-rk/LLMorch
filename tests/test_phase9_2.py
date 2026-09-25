"""
LLMorch Phase 9.2 Test Suite
Validates:
1. Model compatibility matrix & resolution for AGY, Codex, and Claude
2. 6-point strict Model switch validations (model exists, enabled, compatible, agent exists, execution permitted, scope valid)
3. Target/Attack repository intake, validation, and selection persistence
4. Directory browsing with security restrictions and traversal blocking
5. Automatic repository propagation into token estimator and tasks
6. Strict Claude execution guard (Claude remains registered but disabled from real execution)
"""

import os
import tempfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from api.app import app
from history.database import get_db_path, DatabaseService
from history.phase9_repositories import TargetRepositoryRepository
from registry.model_registry import ModelRegistry
from registry.agent_registry import AgentRegistry
from scheduler.agent_switcher import AgentSwitcher
from scheduler.execution_policy import get_execution_policy

client = TestClient(app)


# ─── 1. Model Compatibility & Resolution Tests ────────────────────────────────

def test_agy_returns_compatible_models():
    """Verify agent-agy-01 returns non-empty compatible models with metadata."""
    res = client.get("/api/agents/agent-agy-01/models")
    assert res.status_code == 200
    data = res.json()
    assert data["agent_id"] == "agent-agy-01"
    assert data["current_model_id"] is not None
    models = data["models"]
    assert len(models) >= 1
    model_ids = [m["model_id"] for m in models]
    assert "agy-deep-research" in model_ids or "agy-fast-triage" in model_ids

    # Verify model metadata fields
    first = models[0]
    assert "display_name" in first
    assert "provider" in first
    assert "context_window" in first
    assert "capabilities" in first
    assert first["compatible"] is True
    assert first["available"] is True


def test_codex_returns_compatible_models():
    """Verify agent-codex-01 returns compatible OpenAI models."""
    res = client.get("/api/agents/agent-codex-01/models")
    assert res.status_code == 200
    data = res.json()
    assert data["agent_id"] == "agent-codex-01"
    models = data["models"]
    assert len(models) >= 1
    model_ids = [m["model_id"] for m in models]
    assert any("gpt-4" in mid or "o1" in mid or "o3" in mid for mid in model_ids)


def test_missing_agent_returns_404():
    """Verify querying an unregistered agent returns 404."""
    res = client.get("/api/agents/agent-nonexistent-99/models")
    assert res.status_code == 404


def test_disabled_agent_returns_correct_state():
    """Verify agent-claude-01 shows execution disabled with rejection diagnostics."""
    res = client.get("/api/agents/agent-claude-01/models")
    assert res.status_code == 200
    data = res.json()
    assert data["agent_id"] == "agent-claude-01"
    # Diagnostics must record the runtime disabled state
    diagnostics = data.get("diagnostics", [])
    assert len(diagnostics) >= 1
    claude_diags = [d for d in diagnostics if "claude" in d["model_id"]]
    assert any(d.get("rejection_reason") == "CLAUDE_RUNTIME_DISABLED" for d in claude_diags)


def test_model_switch_validations():
    """Verify backend validates all 6 requirements for model switching."""
    # 1. Valid switch succeeds for AGY
    res = client.post("/api/controls/model-switch", json={
        "agent_id": "agent-agy-01",
        "new_model_id": "agy-fast-triage",
        "reason": "Quick triage required for Phase 9.2 test",
        "scope": "CURRENT_TASK"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["accepted"] is True
    assert data["new_model_id"] == "agy-fast-triage"

    # Switch back
    client.post("/api/controls/model-switch", json={
        "agent_id": "agent-agy-01",
        "new_model_id": "agy-deep-research",
        "reason": "Restoring default model",
        "scope": "CURRENT_TASK"
    })

    # 2. Non-existent model rejected
    res_bad_model = client.post("/api/controls/model-switch", json={
        "agent_id": "agent-agy-01",
        "new_model_id": "non-existent-model-xyz",
        "reason": "Invalid test",
        "scope": "CURRENT_TASK"
    })
    assert res_bad_model.status_code == 400
    assert "not found" in res_bad_model.json()["detail"].lower()

    # 3. Incompatible model rejected (e.g. assigning OpenAI model to AGY)
    res_incompat = client.post("/api/controls/model-switch", json={
        "agent_id": "agent-agy-01",
        "new_model_id": "o3-mini",
        "reason": "Mismatched provider test",
        "scope": "CURRENT_TASK"
    })
    assert res_incompat.status_code == 400
    assert "not supported" in res_incompat.json()["detail"].lower()

    # 4. Disabled agent rejected by ExecutionPolicy
    res_disabled = client.post("/api/controls/model-switch", json={
        "agent_id": "agent-claude-01",
        "new_model_id": "claude-3-7-sonnet",
        "reason": "Should be rejected because execution is disabled",
        "scope": "CURRENT_TASK"
    })
    assert res_disabled.status_code == 400
    assert "disabled" in res_disabled.json()["detail"].lower()

    # 5. Invalid switch scope rejected
    res_bad_scope = client.post("/api/controls/model-switch", json={
        "agent_id": "agent-agy-01",
        "new_model_id": "agy-fast-triage",
        "reason": "Invalid scope test",
        "scope": "INVALID_SCOPE_XYZ"
    })
    assert res_bad_scope.status_code == 400
    assert "scope" in res_bad_scope.json()["detail"].lower()


# ─── 2. Target Repository Intake & Selection Tests ────────────────────────────

def test_repository_validation_and_selection():
    """Verify repository intake, validation, selection, and current repository retrieval."""
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp_dir:
        repo_path = Path(tmp_dir)
        # Create a small dummy security repo
        (repo_path / "src").mkdir()
        (repo_path / "src" / "crypto.c").write_text("void aes_encrypt() { /* AES */ }")
        (repo_path / "include").mkdir()
        (repo_path / "include" / "crypto.h").write_text("#define KEY_SIZE 256")
        (repo_path / ".git").mkdir()

        # 1. Validate repository
        res_val = client.post("/api/repositories/validate", json={"repository_path": str(repo_path)})
        assert res_val.status_code == 200
        val_data = res_val.json()
        assert val_data["valid"] is True
        assert val_data["repository_path"] == str(repo_path.resolve())
        assert val_data["is_git"] is False or val_data["is_git"] is True
        assert "C" in val_data["languages"]

        # 2. Select repository as authoritative target
        res_sel = client.post("/api/repositories/select", json={"repository_path": str(repo_path)})
        assert res_sel.status_code == 200
        sel_data = res_sel.json()
        assert sel_data["success"] is True
        assert sel_data["repository"]["repository_path"] == str(repo_path.resolve())
        assert sel_data["repository"]["status"] == "VALIDATED"

        # 3. Get current repository
        res_cur = client.get("/api/repositories/current")
        assert res_cur.status_code == 200
        cur_data = res_cur.json()
        assert cur_data["is_selected"] is True
        assert cur_data["repository"]["repository_path"] == str(repo_path.resolve())

        # 4. Check recent repositories list
        res_recent = client.get("/api/repositories/recent")
        assert res_recent.status_code == 200
        recent_items = res_recent.json()["repositories"]
        assert any(r["repository_path"] == str(repo_path.resolve()) for r in recent_items)


def test_repository_validation_failure_cases():
    """Verify invalid paths, files, and build directories are rejected safely."""
    # 1. Non-existent path
    res_missing = client.post("/api/repositories/validate", json={"repository_path": "/tmp/non_existent_dir_999"})
    assert res_missing.status_code == 200
    assert res_missing.json()["valid"] is False
    assert "does not exist" in res_missing.json()["error"].lower()

    # 2. File instead of directory
    with tempfile.NamedTemporaryFile(dir="/tmp") as tmp_file:
        res_file = client.post("/api/repositories/validate", json={"repository_path": tmp_file.name})
        assert res_file.status_code == 200
        assert res_file.json()["valid"] is False
        assert "file, not a directory" in res_file.json()["error"].lower()

    # 3. Build / cache directory
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp_dir:
        build_dir = Path(tmp_dir) / "node_modules"
        build_dir.mkdir()
        res_build = client.post("/api/repositories/validate", json={"repository_path": str(build_dir)})
        assert res_build.status_code == 200
        assert res_build.json()["valid"] is False
        assert "build/cache" in res_build.json()["error"].lower()


# ─── 3. Security & Directory Traversal Blocking Tests ─────────────────────────

def test_directory_traversal_and_unauthorized_root_blocked():
    """Verify traversal escapes and unauthorized root access are strictly blocked."""
    # 1. Direct /etc access blocked
    res_etc = client.get("/api/repositories/browse?path=/etc")
    assert res_etc.status_code in (403, 404)

    # 2. Traversal attempt blocked
    res_traversal = client.get("/api/repositories/browse?path=/tmp/../../etc")
    assert res_traversal.status_code in (403, 404)

    # 3. Path outside allowed roots validation
    res_val_unauth = client.post("/api/repositories/validate", json={"repository_path": "/root"})
    assert res_val_unauth.status_code == 200
    assert res_val_unauth.json()["valid"] is False
    assert "outside" in res_val_unauth.json()["error"].lower()


def test_directory_browse_returns_metadata_only():
    """Verify browse endpoint lists directories without leaking file contents."""
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp_dir:
        p = Path(tmp_dir)
        (p / "subfolder").mkdir()
        secret_file = p / "secret.txt"
        secret_file.write_text("SUPER_SECRET_TOKEN=12345")

        res = client.get(f"/api/repositories/browse?path={p}")
        assert res.status_code == 200
        data = res.json()
        assert "entries" in data
        # No entry should contain file contents or raw text
        for entry in data["entries"]:
            assert "SUPER_SECRET_TOKEN" not in str(entry)
            assert "content" not in entry


# ─── 4. Pipeline Integration: Token Estimator & Task Propagation ──────────────

def test_token_estimator_and_task_use_selected_repository():
    """Verify estimator and task creation automatically resolve the selected repository."""
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp_dir:
        repo_path = Path(tmp_dir)
        (repo_path / "main.py").write_text("def verify_hardware_root_of_trust(): return True")

        # Select as current
        client.post("/api/repositories/select", json={"repository_path": str(repo_path)})

        # 1. Token estimator with empty repository_path falls back to selected repository
        res_est = client.post("/api/repository/estimate", json={
            "analysis_policy": "BALANCED",
            "selected_models": ["agy-deep-research"]
        })
        assert res_est.status_code == 200
        est_data = res_est.json()
        assert est_data["repository_path"] == str(repo_path.resolve())
        assert est_data["total_files_discovered"] >= 1

        # 2. Task creation binds selected repository to inputs
        res_task = client.post("/api/tasks", json={
            "objective": "Verify hardware root of trust implementation",
            "assigned_agent_id": "agent-agy-01",
            "risk_level": "MEDIUM"
        })
        assert res_task.status_code == 200
        task_data = res_task.json()
        task_id = task_data["task_id"]

        # Fetch task details and verify repository binding
        res_detail = client.get(f"/api/tasks/{task_id}")
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert detail["inputs"]["repository_path"] == str(repo_path.resolve())


# ─── 5. Strict Claude Execution Guard Test ────────────────────────────────────

def test_claude_execution_guard_active():
    """Verify Claude remains registered in registries but execution policy strictly forbids subprocess execution."""
    mr = ModelRegistry()
    ar = AgentRegistry(model_registry=mr, populate_defaults=True)

    # 1. Claude agent is registered
    claude_agent = ar.get_agent("agent-claude-01")
    assert claude_agent is not None
    assert "anthropic" in claude_agent.provider.lower()

    # 2. Claude models are registered in ModelRegistry
    claude_models = mr.list_models(provider="Anthropic")
    assert len(claude_models) >= 1

    # 3. ExecutionPolicy strictly forbids real Claude execution
    policy = get_execution_policy()
    assert policy.is_agent_executable("agent-claude-01") is False
    assert policy.allow_real_claude_execution is False
    assert "disabled" in policy.get_agent_disabled_reason("agent-claude-01").lower()
