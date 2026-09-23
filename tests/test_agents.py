"""
Unit Tests - Agent Abstraction & Registry
"""

import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from registry.agent_registry import AgentRegistry
from schemas.agent import Agent, AgentInterface
from schemas.health import AgentHealthState
from schemas.agent_selection import AgentSelectionRequest
from schemas.policy import AgentPolicy


def test_agent_registration():
    registry = AgentRegistry()
    agent = Agent(
        agent_id="agent-agy-01",
        provider="antigravity",
        interface=AgentInterface.CLI,
        capabilities=["repository_analysis", "code_analysis"]
    )

    registry.register_agent(agent)
    fetched = registry.get_agent("agent-agy-01")
    assert fetched is not None
    assert fetched.provider == "antigravity"


def test_agent_health_update():
    registry = AgentRegistry()
    agent = Agent(
        agent_id="agent-agy-01",
        provider="antigravity",
        interface=AgentInterface.CLI,
        capabilities=["code_analysis"]
    )
    registry.register_agent(agent)

    registry.update_health("agent-agy-01", AgentHealthState.BUSY)
    assert registry.get_agent("agent-agy-01").health == AgentHealthState.BUSY

    registry.update_health("agent-agy-01", AgentHealthState.UNAVAILABLE)
    assert registry.get_agent("agent-agy-01").availability is False


def test_agent_selection_1_to_4_policy():
    policy = AgentPolicy(min_agents=1, max_agents=4, adaptive=True)
    registry = AgentRegistry(policy)

    # Register 4 agents
    for i in range(1, 5):
        agent = Agent(
            agent_id=f"agent-agy-0{i}",
            provider="antigravity",
            interface=AgentInterface.CLI,
            capabilities=["repository_analysis", "rtl_analysis"]
        )
        registry.register_agent(agent)

    # Request max 2 agents
    req = AgentSelectionRequest(
        required_capabilities=["repository_analysis"],
        max_agents=2
    )
    res = registry.select_agents(req)
    assert len(res.selected_agents) == 2
    assert len(res.fallback_agents) == 2


if __name__ == "__main__":
    pytest.main([__file__])
