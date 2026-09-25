"""
Tests for LLMorch Execution Policy and Claude Runtime Safety Guard (Phase 9.1).
Validates that:
1. AGY is enabled and executable.
2. Codex is enabled and executable.
3. Claude is registered, supported in architecture, but runtime execution is prohibited.
4. Any attempt to invoke ClaudeAdapter.execute_task_sync raises AgentExecutionDisabled before process creation.
5. ContractClaudeAdapter allows contract/mock testing with 0 subprocess calls.
6. AgentSwitcher rejects manual or automatic switches to execution-disabled agents.
"""

import pytest
from schemas.task import Task
from schemas.errors import AgentExecutionDisabled, AgentUnavailableError
from adapters.claude_adapter import ClaudeAdapter, ContractClaudeAdapter
from adapters.agy_adapter import AGYAdapter
from adapters.codex_adapter import CodexAdapter
from scheduler.execution_policy import ExecutionPolicy, get_execution_policy, set_execution_policy
from scheduler.agent_switcher import AgentSwitcher
from registry.agent_registry import AgentRegistry
from registry.model_registry import ModelRegistry
from history.database import DatabaseService


def test_execution_policy_defaults():
    policy = get_execution_policy()
    assert policy.is_agent_executable("agent-agy-01") is True
    assert policy.is_agent_executable("agent-codex-01") is True
    assert policy.is_agent_executable("agent-claude-01") is False
    assert policy.allow_real_claude_execution is False
    assert "Development execution policy" in policy.get_agent_disabled_reason("agent-claude-01")


def test_claude_adapter_rejected_before_subprocess():
    """Assert ClaudeAdapter rejects execution immediately without spawning any subprocess."""
    claude = ClaudeAdapter()
    task = Task(objective="Audit cryptographic boot flow")

    with pytest.raises(AgentExecutionDisabled) as exc_info:
        claude.execute_task_sync(task, "/tmp", "test prompt")

    assert "disabled by policy" in str(exc_info.value)
    assert exc_info.value.details.get("agent_id") == "agent-claude-01"


def test_contract_claude_adapter_allows_mock_execution():
    """Assert ContractClaudeAdapter satisfies contract without real subprocess."""
    mock_claude = ContractClaudeAdapter()
    task = Task(objective="Test mock capability")

    res = mock_claude.execute_task_sync(task, "/tmp", "test prompt")
    assert res["exit_code"] == 0
    assert "Contract Claude" in res["stdout"]
    assert res["run"].status.value == "SUCCEEDED"


def test_agent_switcher_rejects_disabled_claude():
    """Assert AgentSwitcher blocks switching to Claude when execution policy is disabled."""
    db = DatabaseService(":memory:")
    mr = ModelRegistry()
    ar = AgentRegistry(model_registry=mr, populate_defaults=True)
    switcher = AgentSwitcher(db_service=db, agent_registry=ar, model_registry=mr)

    task = Task(objective="Switch test", required_capabilities=["security_review"], assigned_agent_id="agent-agy-01")
    switcher.task_repo.save(task)

    with pytest.raises(AgentUnavailableError) as exc_info:
        switcher.switch_agent(
            task_id=task.task_id,
            new_agent_id="agent-claude-01",
            reason="Analyst requested Claude"
        )

    assert "cannot be switched to" in str(exc_info.value)
    assert "Claude Code real execution is disabled" in str(exc_info.value)


def test_policy_conceptual_re_enabling():
    """Assert policy conceptually supports toggling while ensuring current dev policy defaults to False."""
    custom_policy = ExecutionPolicy(
        allow_real_claude_execution=False,
        allow_real_agy_execution=True,
        allow_real_codex_execution=True
    )
    assert custom_policy.is_agent_executable("agent-claude-01") is False

    # Conceptually enabled in custom policy instance (never applied to global)
    permissive_policy = ExecutionPolicy(
        enabled_agents=["agent-agy-01", "agent-codex-01", "agent-claude-01"],
        disabled_agents=[],
        allow_real_claude_execution=True
    )
    assert permissive_policy.is_agent_executable("agent-claude-01") is True

    # Global policy remains strictly disabled
    assert get_execution_policy().allow_real_claude_execution is False
