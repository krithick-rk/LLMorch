"""
LLMorch Phase 9.1 End-to-End Control Plane Integration Verification Suite
Tests the complete analyst lifecycle:
1. Repository intake & token estimation
2. Budget configuration and limit thresholds
3. Agent registry and dynamic model routing (AUTO / POLICY / MANUAL)
4. Task execution with authoritative token tracking
5. Safe agent switching (checkpointing, run retirement, lineage, zero duplicate execution)
6. Dynamic model switching
7. Automatic failover recording
8. Settings and safe credential masking
"""

import os
import sys
import tempfile
import uuid
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_TEST_DB = f"/tmp/llmorch_phase9_1_e2e_{uuid.uuid4().hex[:8]}.db"
os.environ["LLMORCH_DB_PATH"] = _TEST_DB

from fastapi.testclient import TestClient
from api.app import app
from history.database import DatabaseService
from registry.agent_registry import AgentRegistry
from registry.model_registry import ModelRegistry
from token_tracker.accounting import TokenTracker
from scheduler.agent_switcher import AgentSwitcher
from schemas.task import Task
from schemas.run import Run, RunStatus

client = TestClient(app, raise_server_exceptions=True)


@pytest.fixture(scope="module")
def shared_env():
    """Sets up an isolated test repository directory and database."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = Path(tmp_dir) / "target_repo"
        repo_dir.mkdir()
        (repo_dir / "main.c").write_text("int main() { return 0; }")
        (repo_dir / "crypto.c").write_text("// AES hardware register interface\n#define AES_CTRL 0x40001000\nvoid encrypt() {}")
        (repo_dir / "secret.env").write_text("API_KEY=super_secret_quarantined_token\n")

        db = DatabaseService(_TEST_DB)
        mr = ModelRegistry()
        ar = AgentRegistry(model_registry=mr, populate_defaults=True)
        tracker = TokenTracker(db_service=db)
        switcher = AgentSwitcher(db_service=db, agent_registry=ar, model_registry=mr)

        yield {
            "repo_dir": str(repo_dir),
            "db": db,
            "mr": mr,
            "ar": ar,
            "tracker": tracker,
            "switcher": switcher,
        }


@pytest.fixture(autouse=True)
def enforce_test_db(shared_env, monkeypatch):
    """Ensures all API routers use the isolated shared test database regardless of suite collection order."""
    db = shared_env["db"]
    monkeypatch.setenv("LLMORCH_DB_PATH", _TEST_DB)
    monkeypatch.setattr("api.routers.tokens._get_db", lambda: db)
    monkeypatch.setattr("api.routers.controls._get_db", lambda: db)
    monkeypatch.setattr("api.routers.agents._get_db", lambda: db)
    monkeypatch.setattr("api.routers.settings._get_db", lambda: db)
    monkeypatch.setattr("api.routers.tasks._get_db", lambda: db)



def test_e2e_repository_estimation_and_budget(shared_env):
    """E2E Step 1: Repository estimation and budget setup."""
    repo_dir = shared_env["repo_dir"]

    # 1. Estimate repository tokens
    res = client.post("/api/repository/estimate", json={"repo_path": repo_dir})
    assert res.status_code == 200
    est = res.json()

    assert est["total_files_discovered"] >= 2
    assert est["raw_token_estimate"] > 0
    assert est["llm_scoped_token_estimate"] > 0
    assert est["quarantined_secrets_count"] >= 1  # secret.env excluded
    assert est["recommended_budget"] > 0
    assert len(est["breakdown_by_language"]) >= 1

    # 2. Update Run Budget with recommended limit
    rec_budget = est["recommended_budget"]
    b_res = client.put("/api/budgets", json={
        "budget_limit_tokens": rec_budget,
        "warning_threshold_pct": 0.8,
        "exhaustion_threshold_pct": 0.95
    })
    assert b_res.status_code == 200
    budget = b_res.json()
    assert budget["budget_limit"] == rec_budget
    assert budget["status"] == "AVAILABLE"


def test_e2e_agent_model_resolution(shared_env):
    """E2E Step 2: Model registry capability-driven resolution."""
    # 1. List models
    res = client.get("/api/models")
    assert res.status_code == 200
    models = res.json()["items"]
    assert len(models) >= 4

    # 2. Check model capabilities for AGY
    res_agent = client.get("/api/agents/agent-agy-01/models")
    assert res_agent.status_code == 200
    agent_models = res_agent.json()
    assert len(agent_models) >= 1
    assert any("agy" in m["model_id"] for m in agent_models)


def test_e2e_task_execution_token_tracking_and_switching(shared_env):
    """E2E Step 3: Task execution, token consumption, and safe agent switch."""
    switcher = shared_env["switcher"]
    tracker = shared_env["tracker"]

    # 1. Create a task and run
    task = Task(task_id="task-e2e-1", objective="Analyze AES register boundary", assigned_agent_id="agent-agy-01")
    switcher.task_repo.save(task)
    run = Run(task_id="task-e2e-1", agent_id="agent-agy-01", workspace_id="ws-e2e-1", environment_fingerprint="fp-1", status=RunStatus.RUNNING)
    switcher.run_repo.save(run)

    # 2. Record token usage during analysis
    tracker.record_usage(
        task_id="task-e2e-1",
        run_id=run.run_id,
        agent_id="agent-agy-01",
        model_id="agy-pro-reasoner",
        input_tokens_actual=2500,
        output_tokens_actual=800,
        stage="reconnaissance"
    )

    tokens_res = client.get("/api/tokens")
    assert tokens_res.status_code == 200
    summary = tokens_res.json()
    assert summary["total_tokens_actual"] == 3300
    assert summary["by_agent"]["agent-agy-01"]["actual"] == 3300

    # 3. Analyst triggers manual agent switch to Codex
    switch_res = client.post("/api/controls/agent-switch", json={
        "task_id": "task-e2e-1",
        "new_agent_id": "agent-codex-01",
        "reason": "Deep reasoning required on AES cryptanalysis",
        "resume_action": "RESUME_FROM_CHECKPOINT"
    })
    assert switch_res.status_code == 200
    outcome = switch_res.json()
    assert outcome["accepted"] is True
    assert outcome["previous_agent_id"] == "agent-agy-01"
    assert outcome["new_agent_id"] == "agent-codex-01"
    assert outcome["checkpoint_id"] is not None

    # Verify old run retired to prevent duplicate execution
    old_run = switcher.run_repo.get(run.run_id)
    assert old_run.status == RunStatus.CANCELLED

    # Verify new run has parent lineage
    new_run = switcher.run_repo.get(outcome["new_run_id"])
    assert new_run.parent_run_id == run.run_id
    assert new_run.agent_id == "agent-codex-01"

    # Verify switch audit log queryable via API
    sw_res = client.get("/api/controls/switches?task_id=task-e2e-1")
    assert sw_res.status_code == 200
    switches = sw_res.json()["items"]
    assert len(switches) >= 1
    assert switches[0]["switch_type"] == "MANUAL"
    assert switches[0]["new_agent_id"] == "agent-codex-01"


def test_e2e_model_switching_and_settings_persistence(shared_env):
    """E2E Step 4: Model switching and configuration settings persistence."""
    # 1. Switch model on Codex to o3-mini
    ms_res = client.post("/api/controls/model-switch", json={
        "agent_id": "agent-codex-01",
        "new_model_id": "o3-mini",
        "reason": "Optimize for low-latency reasoning",
        "scope": "CURRENT_TASK"
    })
    assert ms_res.status_code == 200
    ms = ms_res.json()
    assert ms["accepted"] is True
    assert ms["new_model_id"] == "o3-mini"

    # 2. Get and update settings
    settings_res = client.get("/api/settings")
    assert settings_res.status_code == 200
    current_settings = settings_res.json()
    assert "tokens" in current_settings

    # Update settings
    current_settings["tokens"]["run_budget"] = 250000
    current_settings["models"]["policy"] = "FAST_TRIAGE"

    upd_res = client.put("/api/settings", json={
        "tokens": current_settings["tokens"],
        "models": current_settings["models"],
    })
    assert upd_res.status_code == 200
    saved = upd_res.json()
    assert saved["tokens"]["run_budget"] == 250000
    assert saved["models"]["policy"] == "FAST_TRIAGE"

    # 3. Verify security settings masks secrets
    assert "credentials_status" in saved["security"]
    assert "antigravity" in saved["security"]["credentials_status"]
    masked = saved["security"]["credentials_status"]["antigravity"]["masked"]
    assert "••••" in masked or "SET" in masked
    assert "super_secret" not in masked
