"""
Unit & Integration Tests - Phase 2 Generic Adapters & Model Independence
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters.base import BaseAgentAdapter
from adapters.agy_adapter import AGYAdapter
from adapters.claude_adapter import ClaudeAdapter, ContractClaudeAdapter
from registry.agent_registry import AgentRegistry
from schemas.agent import Agent, AgentInterface
from schemas.health import AgentHealthState
from schemas.agent_selection import AgentSelectionRequest
from schemas.task_result import TaskResult
from schemas.task import Task
from schemas.errors import AgentExecutionDisabled
from orchestrator.investigation import InvestigationWorkflow
from history.database import DatabaseService


def test_adapters_satisfy_interface():
    agy = AGYAdapter()
    claude = ClaudeAdapter()

    assert isinstance(agy, BaseAgentAdapter)
    assert isinstance(claude, BaseAgentAdapter)
    assert "security_review" in agy.capabilities()
    assert "security_review" in claude.capabilities()


def test_agent_registry_multi_agent():
    registry = AgentRegistry()
    agy = AGYAdapter()
    claude = ClaudeAdapter()

    agent1 = Agent(
        agent_id="agent-agy-01",
        provider="antigravity",
        interface=AgentInterface.CLI,
        capabilities=agy.capabilities(),
        health=agy.health()
    )
    agent2 = Agent(
        agent_id="agent-claude-01",
        provider="anthropic",
        interface=AgentInterface.CLI,
        capabilities=claude.capabilities(),
        health=claude.health()
    )

    registry.register_agent(agent1)
    registry.register_agent(agent2)

    assert len(registry.list_agents()) == 2
    assert registry.get_agent("agent-agy-01").provider == "antigravity"
    assert registry.get_agent("agent-claude-01").provider == "anthropic"


def test_capability_routing():
    registry = AgentRegistry()
    agy = AGYAdapter()
    claude = ClaudeAdapter()

    registry.register_agent(Agent(agent_id="agent-agy-01", provider="antigravity", interface=AgentInterface.CLI, capabilities=agy.capabilities()))
    registry.register_agent(Agent(agent_id="agent-claude-01", provider="anthropic", interface=AgentInterface.CLI, capabilities=claude.capabilities()))

    req = AgentSelectionRequest(required_capabilities=["security_review"], max_agents=2)
    res = registry.select_agents(req)
    assert len(res.selected_agents) == 2
    ids = [a.agent_id for a in res.selected_agents]
    assert "agent-agy-01" in ids
    assert "agent-claude-01" in ids


def test_result_normalization_cross_model():
    agy = AGYAdapter()
    claude = ClaudeAdapter()

    raw_agy = '{"hypothesis": "Buffer overflow in DMA", "affected_locations": [{"file_path": "dma.c"}], "confidence": 0.9}'
    raw_claude = '{"hypothesis": "Buffer overflow in DMA", "affected_locations": [{"file_path": "dma.c"}], "confidence": 0.88}'

    res1 = agy.normalize_result(raw_agy)
    res2 = claude.normalize_result(raw_claude)

    assert isinstance(res1, TaskResult)
    assert isinstance(res2, TaskResult)
    assert res1.hypothesis == res2.hypothesis
    assert res1.affected_locations == res2.affected_locations


def test_model_independence_execution_flow():
    # Run same logical investigation task with AGY agent
    db1 = DatabaseService(":memory:")
    wf_agy = InvestigationWorkflow(repo_path=str(PROJECT_ROOT), target_component="schemas", preferred_agent_id="agent-agy-01", db_service=db1)
    res_agy = wf_agy.run()
    assert res_agy["assigned_agent"] == "agent-agy-01"
    assert res_agy["provider"] == "antigravity"

    # Run same logical investigation task with Claude agent (using ContractClaudeAdapter to prevent real CLI invocation)
    db2 = DatabaseService(":memory:")
    wf_claude = InvestigationWorkflow(
        repo_path=str(PROJECT_ROOT),
        target_component="schemas",
        preferred_agent_id="agent-claude-01",
        db_service=db2,
        custom_adapters={"agent-claude-01": ContractClaudeAdapter()}
    )
    res_claude = wf_claude.run()
    assert res_claude["assigned_agent"] == "agent-claude-01"
    assert res_claude["provider"] == "anthropic"

    # Verify both produce identical output structure
    assert res_agy["task_status"] in ("SUCCEEDED", "FAILED", "READY_FOR_REVIEW")
    assert res_claude["task_status"] in ("SUCCEEDED", "FAILED", "READY_FOR_REVIEW")
    assert res_agy["finding_state"] == res_claude["finding_state"]


def test_failure_isolation():
    # Verify Claude execution is rejected by safety policy before subprocess creation
    claude = ClaudeAdapter()
    task = Task(objective="Fail isolation test")

    with pytest.raises(AgentExecutionDisabled):
        claude.execute_task_sync(task, "/tmp", "prompt")



if __name__ == "__main__":
    pytest.main([__file__])
