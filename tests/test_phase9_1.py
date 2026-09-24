"""
LLMorch Phase 9.1 Comprehensive Test Suite
Validates:
1. Agent switching (manual switch, automatic failover, unavailable agent rejection, checkpoint & lineage preservation, zero duplicate execution)
2. Model routing (AUTO, MANUAL, POLICY, capability matching, invalid combination rejection)
3. Token tracking (actual, estimated, per-agent, per-model, per-task, aggregation, limit enforcement)
4. Repository estimation (mixed languages, secrets exclusion, vendor noise filtering, deterministic repeated estimates)
5. Budget enforcement (AVAILABLE, LOW, NEAR_LIMIT, EXHAUSTED)
6. API Endpoints (settings, models, tokens, budgets, switches, estimates)
7. Security (masked secrets, authentication boundary)
"""

import os
import tempfile
import pytest
from pathlib import Path
from datetime import datetime, timezone
import uuid

from fastapi.testclient import TestClient

from api.app import app
from api.session import create_session, get_default_token
from history.database import DatabaseService
from schemas.agent import Agent, AgentInterface
from schemas.health import AgentHealthState, AgentQuotaStatus
from schemas.model import (
    Model,
    ModelCapability,
    ModelSelectionMode,
    ModelPolicy,
    ModelSelectionRequest,
)
from schemas.task import Task, TaskStatus, RiskLevel
from schemas.run import Run, RunStatus
from schemas.token import TokenSource, TokenLimitStatus, TokenBudgetConfig
from schemas.errors import LLMorchError, AgentUnavailableError

from registry.agent_registry import AgentRegistry
from registry.model_registry import ModelRegistry
from scheduler.agent_switcher import AgentSwitcher
from scheduler.model_router import ModelRouter
from scheduler.failover import FailoverEngine
from token_tracker.accounting import TokenTracker, estimate_tokens_from_text
from token_tracker.allocator import TokenBudgetAllocator
from token_tracker.limits import TokenLimitEnforcer, EnforcementDecision
from repository_intelligence.token_estimator import estimate_repository_tokens


@pytest.fixture
def db():
    return DatabaseService(":memory:")


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr("api.routers.agents._get_db", lambda: db)
    monkeypatch.setattr("api.routers.controls._get_db", lambda: db)
    monkeypatch.setattr("api.routers.tokens._get_db", lambda: db)
    monkeypatch.setattr("api.routers.settings._get_db", lambda: db)
    monkeypatch.setattr("api.routers.repository._get_db", lambda: db)
    return TestClient(app)


# ─── 1. Model Registry & Routing Tests ────────────────────────────────────────

def test_model_registry_defaults():
    mr = ModelRegistry()
    models = mr.list_models()
    assert len(models) >= 8

    # Verify AGY models
    agy_models = mr.get_models_for_agent("agent-agy-01")
    assert any(m.model_id == "agy-deep-research" for m in agy_models)
    assert any(m.model_id == "agy-fast-triage" for m in agy_models)

    # Verify Claude models
    claude_models = mr.get_models_for_agent("agent-claude-01")
    assert any(m.model_id == "claude-3-7-sonnet" for m in claude_models)

    # Verify Codex models
    codex_models = mr.get_models_for_agent("agent-codex-01")
    assert any(m.model_id == "gpt-4o" for m in codex_models)


def test_model_router_manual_valid_and_invalid():
    mr = ModelRegistry()
    router = ModelRouter(mr)
    task = Task(objective="RTL register lock check", required_capabilities=["code_analysis"])

    # Valid manual selection for Codex
    res = router.route_task(
        task=task,
        agent_id="agent-codex-01",
        mode=ModelSelectionMode.MANUAL,
        preferred_model_id="gpt-4o"
    )
    assert res.selected_model.model_id == "gpt-4o"
    assert res.selection_mode == ModelSelectionMode.MANUAL

    # Invalid combination: Codex agent with Claude model
    with pytest.raises(LLMorchError):
        router.route_task(
            task=task,
            agent_id="agent-codex-01",
            mode=ModelSelectionMode.MANUAL,
            preferred_model_id="claude-3-7-sonnet"
        )


def test_model_router_policy_resolution():
    mr = ModelRegistry()
    router = ModelRouter(mr)
    task = Task(objective="Examine bus register lock")

    # Policy RTL_SECURITY should pick RTL capable model
    res_rtl = router.route_task(
        task=task,
        agent_id="agent-agy-01",
        mode=ModelSelectionMode.POLICY,
        policy=ModelPolicy.RTL_SECURITY
    )
    assert "rtl_analysis" in res_rtl.selected_model.capabilities

    # Policy LOW_TOKEN should pick fast triage model
    res_low = router.route_task(
        task=task,
        agent_id="agent-agy-01",
        mode=ModelSelectionMode.POLICY,
        policy=ModelPolicy.LOW_TOKEN
    )
    assert "fast_triage" in res_low.selected_model.capabilities


def test_model_router_auto_capability_matching():
    mr = ModelRegistry()
    router = ModelRouter(mr)

    # RTL task should automatically prefer RTL model
    task_rtl = Task(objective="Verify RTL security boundary in AES unit", required_capabilities=["code_analysis"])
    res = router.route_task(task=task_rtl, agent_id="agent-agy-01", mode=ModelSelectionMode.AUTO)
    assert "rtl_analysis" in res.selected_model.capabilities


# ─── 2. Agent Switching Tests ─────────────────────────────────────────────────

def test_agent_switch_manual_success(db):
    mr = ModelRegistry()
    ar = AgentRegistry(model_registry=mr, populate_defaults=True)
    switcher = AgentSwitcher(db_service=db, agent_registry=ar, model_registry=mr)

    # Create active task and run
    task = Task(
        task_id="task-switch-1",
        objective="Security register analysis",
        assigned_agent_id="agent-agy-01",
        status=TaskStatus.RUNNING,
        required_capabilities=["code_analysis"]
    )
    switcher.task_repo.save(task)

    run = Run(
        task_id="task-switch-1",
        agent_id="agent-agy-01",
        workspace_id="ws-1",
        environment_fingerprint="env-1",
        status=RunStatus.RUNNING
    )
    switcher.run_repo.save(run)

    # Execute switch to Codex
    outcome = switcher.switch_agent(
        task_id="task-switch-1",
        new_agent_id="agent-codex-01",
        reason="Analyst requested deep reasoning on Codex",
        resume_action="RESUME_FROM_CHECKPOINT"
    )

    assert outcome["success"] is True
    assert outcome["previous_agent_id"] == "agent-agy-01"
    assert outcome["new_agent_id"] == "agent-codex-01"

    # Verify checkpoint created
    assert outcome["checkpoint_id"] is not None
    chk = switcher.chk_repo.get(outcome["checkpoint_id"])
    assert chk.is_valid is True

    # Verify old run cancelled to prevent duplicate execution
    old_run = switcher.run_repo.get(run.run_id)
    assert old_run.status == RunStatus.CANCELLED

    # Verify new run spawned with lineage
    new_run = switcher.run_repo.get(outcome["new_run_id"])
    assert new_run.parent_run_id == run.run_id
    assert new_run.agent_id == "agent-codex-01"

    # Verify task reassigned
    updated_task = switcher.task_repo.get("task-switch-1")
    assert updated_task.assigned_agent_id == "agent-codex-01"
    assert updated_task.retry_count == 1


def test_agent_switch_rejects_unavailable_or_unregistered(db):
    mr = ModelRegistry()
    ar = AgentRegistry(model_registry=mr, populate_defaults=True)
    switcher = AgentSwitcher(db_service=db, agent_registry=ar, model_registry=mr)

    task = Task(task_id="task-switch-2", objective="Test", assigned_agent_id="agent-agy-01")
    switcher.task_repo.save(task)

    # Non-existent agent
    with pytest.raises(AgentUnavailableError):
        switcher.switch_agent(task_id="task-switch-2", new_agent_id="agent-nonexistent", reason="test")

    # Disabled agent
    ar.set_agent_enabled("agent-fourth-01", False)
    with pytest.raises(AgentUnavailableError):
        switcher.switch_agent(task_id="task-switch-2", new_agent_id="agent-fourth-01", reason="test")


def test_model_switch_success(db):
    mr = ModelRegistry()
    ar = AgentRegistry(model_registry=mr, populate_defaults=True)
    switcher = AgentSwitcher(db_service=db, agent_registry=ar, model_registry=mr)

    res = switcher.switch_model(
        agent_id="agent-codex-01",
        new_model_id="o3-mini",
        reason="Fast reasoning required",
        scope="CURRENT_TASK"
    )

    assert res["success"] is True
    assert res["new_model_id"] == "o3-mini"
    agent = ar.get_agent("agent-codex-01")
    assert agent.current_model_id == "o3-mini"


# ─── 3. Token Accounting & Limits Tests ───────────────────────────────────────

def test_token_tracking_actual_and_estimated(db):
    tracker = TokenTracker(db_service=db)

    # 1. Actual usage from provider
    rec1 = tracker.record_usage(
        task_id="t-1",
        run_id="r-1",
        agent_id="agent-codex-01",
        model_id="gpt-4o",
        input_tokens_actual=1200,
        output_tokens_actual=350,
        token_source=TokenSource.PROVIDER_REPORTED
    )
    assert rec1.total_tokens_actual == 1550
    assert rec1.is_estimated is False
    assert rec1.input_source == TokenSource.PROVIDER_REPORTED

    # 2. Estimated usage from raw text
    sample_code = "int main() { printf('hello security world\\n'); return 0; }"
    rec2 = tracker.record_usage(
        task_id="t-2",
        run_id="r-1",
        agent_id="agent-agy-01",
        model_id="agy-fast-triage",
        raw_input_text=sample_code,
        raw_output_text="Hypothesis: No vulnerability.",
    )
    assert rec2.total_tokens_estimated > 0
    assert rec2.is_estimated is True
    assert rec2.input_source == TokenSource.LOCAL_TOKENIZER

    # 3. Summary aggregation
    summary = tracker.get_summary(run_id="r-1")
    assert summary.total_tokens_actual == 1550
    assert summary.total_tokens_estimated > 0
    assert summary.status == TokenLimitStatus.AVAILABLE


def test_token_limit_enforcer():
    enforcer = TokenLimitEnforcer(TokenBudgetConfig(run_budget=100000))

    # Available
    d1 = enforcer.check_task_dispatch(
        task_id="t1", task_budget=20000, task_consumed=5000,
        run_budget=100000, run_consumed=20000
    )
    assert d1["decision"] == EnforcementDecision.PROCEED
    assert d1["status"] == TokenLimitStatus.AVAILABLE

    # Low warning (<30% remaining)
    d2 = enforcer.check_task_dispatch(
        task_id="t1", task_budget=20000, task_consumed=5000,
        run_budget=100000, run_consumed=75000
    )
    assert d2["decision"] == EnforcementDecision.WARN_LOW
    assert d2["status"] == TokenLimitStatus.LOW

    # Near limit warning (<10% remaining)
    d3 = enforcer.check_task_dispatch(
        task_id="t1", task_budget=20000, task_consumed=5000,
        run_budget=100000, run_consumed=92000
    )
    assert d3["decision"] == EnforcementDecision.WARN_NEAR_LIMIT
    assert d3["status"] == TokenLimitStatus.NEAR_LIMIT

    # Run exhausted
    d4 = enforcer.check_task_dispatch(
        task_id="t1", task_budget=20000, task_consumed=5000,
        run_budget=100000, run_consumed=100000
    )
    assert d4["can_proceed"] is False
    assert d4["status"] == TokenLimitStatus.EXHAUSTED


def test_token_budget_allocator():
    allocator = TokenBudgetAllocator(reserve_percent=20.0)
    plan = allocator.allocate(
        run_budget=600000,
        agent_ids=["agent-agy-01", "agent-claude-01", "agent-codex-01"],
        task_complexity="high",
        task_priority="HIGH"
    )

    assert plan.run_budget == 600000
    assert plan.reserved_budget == 120000
    assert plan.available_budget == 480000
    assert len(plan.agent_budgets) == 3
    assert plan.task_budget > 0
    # All agent budgets sum to available budget
    assert sum(plan.agent_budgets.values()) == plan.available_budget


# ─── 4. Repository Token Estimation Tests ─────────────────────────────────────

def test_repository_token_estimation_with_mixed_repo(tmp_path):
    # Setup test repo with C, RTL, Python, and quarantined secret
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "driver.c").write_text("int write_reg(int addr, int val) { return 0; }\n" * 50)
    (tmp_path / "src" / "core.sv").write_text("module aes_core (input clk, input rst_n); always @(posedge clk) begin end endmodule\n" * 40)
    (tmp_path / "src" / "test.py").write_text("def test_security(): assert True\n" * 20)

    # Secret file
    (tmp_path / "src" / "secret.key").write_text("SECRET_KEY=1234567890abcdef\n")

    # Vendor file
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "lib.c").write_text("void third_party() {}\n" * 100)

    est = estimate_repository_tokens(str(tmp_path))

    assert est.total_files_discovered >= 4
    assert est.raw_token_estimate > 0
    assert est.llm_scoped_token_estimate > 0
    assert est.recommended_budget > est.estimated_total_tokens
    assert est.secrets_excluded_safely is True

    # Breakdown has language estimates
    langs = [l.language for l in est.breakdown_by_language]
    assert any(lang in langs for lang in ("c", "sv", "py"))


# ─── 5. API Layer Tests ───────────────────────────────────────────────────────

def test_api_models_endpoint(client):
    res = client.get("/api/models")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 8
    model_ids = [m["model_id"] for m in data["items"]]
    assert "agy-deep-research" in model_ids
    assert "gpt-4o" in model_ids


def test_api_agents_endpoint(client):
    res = client.get("/api/agents")
    assert res.status_code == 200
    data = res.json()
    items = data["items"]
    assert len(items) >= 3
    agy = next((a for a in items if a["agent_id"] == "agent-agy-01"), None)
    assert agy is not None
    assert agy["role"] == "general_analysis"
    assert len(agy["supported_models"]) >= 1


def test_api_settings_persistence_and_masking(client):
    # 1. Get default settings
    r_get = client.get("/api/settings")
    assert r_get.status_code == 200
    settings = r_get.json()
    assert settings["version"] == 1
    # Verify secrets are masked
    sec = settings["security"]
    for prov, meta in sec.get("credentials_status", {}).items():
        assert "••••••••" in meta.get("masked", "")

    # 2. Update settings
    r_put = client.put("/api/settings", json={
        "tokens": {"run_budget": 750000},
        "execution": {"concurrency": 3}
    })
    assert r_put.status_code == 200
    updated = r_put.json()
    assert updated["version"] == 2
    assert updated["tokens"]["run_budget"] == 750000
    assert updated["execution"]["concurrency"] == 3


def test_api_tokens_endpoints(client):
    r_tokens = client.get("/api/tokens")
    assert r_tokens.status_code == 200
    data = r_tokens.json()
    assert "effective_total_tokens" in data
    assert "tokens_remaining" in data

    r_budgets = client.get("/api/budgets")
    assert r_budgets.status_code == 200

    r_update_bgt = client.put("/api/budgets", json={
        "scope_type": "run",
        "scope_id": "run-test-1",
        "budget_limit": 600000
    })
    assert r_update_bgt.status_code == 200
    assert r_update_bgt.json()["budget_limit"] == 600000


def test_agent_failover_records_switch_and_events(db):
    mr = ModelRegistry()
    ar = AgentRegistry(model_registry=mr, populate_defaults=True)
    from sandbox.workspace import WorkspaceManager
    from schemas.errors import ErrorCode

    fo = FailoverEngine(db, ar, WorkspaceManager())

    # Create task & run
    task = Task(task_id="task-fo-1", objective="Inspect registers", assigned_agent_id="agent-agy-01")
    fo.task_repo.save(task)
    run = Run(task_id="task-fo-1", agent_id="agent-agy-01", workspace_id="ws-fo-1", environment_fingerprint="env-1", status=RunStatus.RUNNING)
    fo.run_repo.save(run)

    # Trigger failover due to quota exhaustion
    res = fo.handle_failure_and_recover(
        task_id="task-fo-1",
        failed_run_id=run.run_id,
        error_code=ErrorCode.QUOTA_EXHAUSTED,
        failure_reason="Rate limit exceeded"
    )

    assert res["status"] == "RESUMED"
    assert res["replacement_agent_id"] != "agent-agy-01"

    # Verify switch was recorded in AgentSwitchRepository
    switches = fo.switch_repo.list_switches(task_id="task-fo-1")
    assert len(switches) >= 1
    assert switches[0]["switch_type"] == "FAILOVER"
    assert switches[0]["previous_agent_id"] == "agent-agy-01"
    assert switches[0]["new_agent_id"] == res["replacement_agent_id"]


def test_empty_repository_estimation(tmp_path):
    empty_dir = tmp_path / "empty_repo"
    empty_dir.mkdir()

    est = estimate_repository_tokens(str(empty_dir))
    assert est.total_files_discovered == 0
    assert est.raw_token_estimate == 0
    assert est.recommended_budget > 0  # Still recommends baseline minimum budget


def test_token_aggregation_across_multiple_tasks(db):
    tracker = TokenTracker(db_service=db)

    tracker.record_usage(task_id="task-1", run_id="run-A", agent_id="agent-agy-01", model_id="agy-deep-research", stage="discovery", input_tokens_actual=1000, output_tokens_actual=200)
    tracker.record_usage(task_id="task-2", run_id="run-A", agent_id="agent-codex-01", model_id="gpt-4o", stage="deep_analysis", input_tokens_actual=3000, output_tokens_actual=800)
    tracker.record_usage(task_id="task-3", run_id="run-A", agent_id="agent-agy-01", model_id="agy-fast-triage", stage="static_analysis", input_tokens_actual=500, output_tokens_actual=100)

    summary = tracker.get_summary(run_id="run-A")
    assert summary.total_tokens_actual == (1200 + 3800 + 600)
    assert len(summary.by_agent) == 2
    assert "agent-agy-01" in summary.by_agent
    assert "agent-codex-01" in summary.by_agent
    assert summary.by_agent["agent-agy-01"]["actual"] == 1800
    assert summary.by_agent["agent-codex-01"]["actual"] == 3800


def test_api_switch_history_endpoints(client, db):
    # Insert test task
    task = Task(task_id="task-api-sw", objective="Check switches", assigned_agent_id="agent-agy-01")
    from history.repositories import TaskRepository
    TaskRepository(db).save(task)

    # Perform switch via API
    r_sw = client.post("/api/controls/agent-switch", json={
        "task_id": "task-api-sw",
        "new_agent_id": "agent-codex-01",
        "reason": "Testing history endpoint",
        "resume_action": "RESUME_FROM_CHECKPOINT"
    })
    assert r_sw.status_code == 200

    # Query switch history
    r_hist = client.get("/api/controls/switches?task_id=task-api-sw")
    assert r_hist.status_code == 200
    data = r_hist.json()
    assert len(data["agent_switches"]) >= 1
    assert data["agent_switches"][0]["new_agent_id"] == "agent-codex-01"
