"""
Unit & Integration Tests - Phase 4 Adaptive Strategy Engine
"""

import pytest
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.task import Task
from schemas.agent import Agent, AgentInterface
from schemas.health import AgentHealthState
from schemas.strategy import StrategyDecision, AgentAssignment
from registry.agent_registry import AgentRegistry
from orchestrator.strategy import StrategyEngine
from orchestrator.investigation import InvestigationWorkflow
from history.database import DatabaseService


def test_strategy_engine_1_agent_selection():
    registry = AgentRegistry()
    registry.register_agent(Agent(agent_id="agent-agy-01", provider="antigravity", interface=AgentInterface.CLI, capabilities=["repository_analysis", "security_review"]))

    engine = StrategyEngine(registry, config={"max_agents": 4})
    task = Task(objective="Fix typo in README", required_capabilities=["repository_analysis", "security_review"])

    decision, assignments = engine.evaluate(task, scoped_paths=["README.md"], precheck_count=0)
    assert decision.chosen_agent_count == 1
    assert len(assignments) == 1
    assert assignments[0].agent_id == "agent-agy-01"
    assert assignments[0].role == "primary_investigation"


def test_strategy_engine_2_agent_selection():
    registry = AgentRegistry()
    registry.register_agent(Agent(agent_id="agent-agy-01", provider="antigravity", interface=AgentInterface.CLI, capabilities=["repository_analysis", "security_review"]))
    registry.register_agent(Agent(agent_id="agent-codex-01", provider="openai", interface=AgentInterface.CLI, capabilities=["repository_analysis", "security_review"]))

    engine = StrategyEngine(registry, config={"max_agents": 4})
    task = Task(objective="Investigate state transition privilege vulnerability in auth module", required_capabilities=["repository_analysis", "security_review"])

    decision, assignments = engine.evaluate(task, scoped_paths=["auth/state.py", "auth/gate.py", "auth/token.py", "auth/session.py"], precheck_count=1)
    assert decision.chosen_agent_count == 2
    assert len(assignments) == 2
    assert decision.estimated_uncertainty in ("HIGH", "MEDIUM")


def test_strategy_engine_3_agent_selection():
    registry = AgentRegistry()
    registry.register_agent(Agent(agent_id="agent-agy-01", provider="antigravity", interface=AgentInterface.CLI, capabilities=["repository_analysis", "security_review"]))
    registry.register_agent(Agent(agent_id="agent-codex-01", provider="openai", interface=AgentInterface.CLI, capabilities=["repository_analysis", "security_review"]))
    registry.register_agent(Agent(agent_id="agent-fourth-01", provider="auxiliary", interface=AgentInterface.CLI, capabilities=["repository_analysis", "security_review"]))

    engine = StrategyEngine(registry, config={"max_agents": 4})
    task = Task(objective="Investigate high complexity crypto key boot lifecycle vulnerability across files", required_capabilities=["repository_analysis", "security_review"])

    paths = [f"crypto/module_{i}.c" for i in range(10)]
    decision, assignments = engine.evaluate(task, scoped_paths=paths, precheck_count=2)
    assert decision.chosen_agent_count == 3
    assert len(assignments) == 3


def test_strategy_engine_4_agent_selection():
    registry = AgentRegistry()
    for i in range(4):
        registry.register_agent(Agent(agent_id=f"agent-0{i+1}", provider="test", interface=AgentInterface.CLI, capabilities=["repository_analysis", "security_review"]))

    engine = StrategyEngine(registry, config={"max_agents": 4})
    task = Task(objective="Investigate critical crypto key auth privilege boot state transition across multi-domain scope", required_capabilities=["repository_analysis", "security_review"])

    paths = [f"domain/file_{i}.c" for i in range(20)]
    decision, assignments = engine.evaluate(task, scoped_paths=paths, precheck_count=3)
    assert decision.chosen_agent_count == 4
    assert len(assignments) == 4


def test_hard_constraint_filtering_unavailable_agent():
    registry = AgentRegistry()
    registry.register_agent(Agent(agent_id="agent-healthy", provider="antigravity", interface=AgentInterface.CLI, capabilities=["security_review"], health=AgentHealthState.AVAILABLE, availability=True))
    registry.register_agent(Agent(agent_id="agent-dead", provider="anthropic", interface=AgentInterface.CLI, capabilities=["security_review"], health=AgentHealthState.UNAVAILABLE, availability=False))

    engine = StrategyEngine(registry, config={"max_agents": 4})
    task = Task(objective="Investigate crypto auth", required_capabilities=["security_review"])

    decision, assignments = engine.evaluate(task, scoped_paths=["crypto.c"], precheck_count=1)
    assert "agent-healthy" in decision.selected_agents
    assert "agent-dead" not in decision.selected_agents
    assert any("agent-dead" in exc for exc in decision.excluded_agents)


def test_budget_constrained_selection():
    registry = AgentRegistry()
    registry.register_agent(Agent(agent_id="agent-agy-01", provider="antigravity", interface=AgentInterface.CLI, capabilities=["security_review"]))
    registry.register_agent(Agent(agent_id="agent-codex-01", provider="openai", interface=AgentInterface.CLI, capabilities=["security_review"]))

    engine = StrategyEngine(registry, config={"max_agents": 4})
    task = Task(objective="Investigate crypto auth", required_capabilities=["security_review"])

    # Low budget forces 1 agent
    decision, assignments = engine.evaluate(task, scoped_paths=["crypto.c"], precheck_count=1, budget_available=10.0)
    assert decision.chosen_agent_count == 1


def test_explicit_count_override():
    registry = AgentRegistry()
    registry.register_agent(Agent(agent_id="agent-agy-01", provider="antigravity", interface=AgentInterface.CLI, capabilities=["security_review"]))
    registry.register_agent(Agent(agent_id="agent-codex-01", provider="openai", interface=AgentInterface.CLI, capabilities=["security_review"]))

    engine = StrategyEngine(registry, config={"max_agents": 4})
    task = Task(objective="Simple task", required_capabilities=["security_review"])

    decision, assignments = engine.evaluate(task, scoped_paths=["simple.c"], precheck_count=0, forced_agent_count=2)
    assert decision.chosen_agent_count == 2


def test_end_to_end_adaptive_workflow_execution():
    db = DatabaseService(":memory:")
    wf = InvestigationWorkflow(
        repo_path=str(PROJECT_ROOT),
        target_component="schemas",
        db_service=db
    )
    res = wf.run()

    assert "strategy_decision" in res
    assert res["chosen_agent_count"] >= 1
    assert "estimated_complexity" in res["strategy_decision"]


if __name__ == "__main__":
    pytest.main([__file__])
