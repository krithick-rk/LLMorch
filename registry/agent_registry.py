"""
LLMorch Agent Registry
Manages agent registration, health state tracking, and capability-driven selection.
Supports 1 to 4 configured agents dynamically.
"""

from typing import Dict, List, Optional
from schemas.agent import Agent, AgentInterface
from schemas.health import AgentHealthState, AgentUsageStatus
from schemas.agent_selection import AgentSelectionRequest, AgentSelectionResult
from schemas.policy import AgentPolicy
from schemas.errors import AgentUnavailableError


class AgentRegistry:
    """
    Central Agent Registry for elastic agent management.
    Never hard-codes agent identity or fixed team roles.
    """

    def __init__(self, policy: Optional[AgentPolicy] = None):
        self.policy = policy or AgentPolicy(min_agents=1, max_agents=4, adaptive=True)
        self._agents: Dict[str, Agent] = {}

    def register_agent(self, agent: Agent) -> Agent:
        """Registers an agent instance in the registry."""
        self._agents[agent.agent_id] = agent
        return agent

    def unregister_agent(self, agent_id: str) -> Optional[Agent]:
        """Removes an agent instance from the registry."""
        return self._agents.pop(agent_id, None)

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Retrieves an agent by identifier."""
        return self._agents.get(agent_id)

    def list_agents(self, filter_health: Optional[AgentHealthState] = None) -> List[Agent]:
        """Lists all registered agents, optionally filtered by health state."""
        agents = list(self._agents.values())
        if filter_health:
            agents = [a for a in agents if a.health == filter_health]
        return agents

    def update_health(self, agent_id: str, health: AgentHealthState, usage: Optional[AgentUsageStatus] = None) -> Agent:
        """Updates health and usage state for a registered agent."""
        agent = self.get_agent(agent_id)
        if not agent:
            raise AgentUnavailableError(f"Agent '{agent_id}' not found in registry")
        agent.health = health
        if usage:
            agent.usage_status = usage
        if health not in (AgentHealthState.AVAILABLE, AgentHealthState.BUSY, AgentHealthState.DEGRADED):
            agent.availability = False
        else:
            agent.availability = True
        return agent

    def select_agents(self, request: AgentSelectionRequest) -> AgentSelectionResult:
        """
        Data-driven agent selection engine.
        Matches required capabilities and health requirements.
        Respects max_agents policy (1 to 4).
        """
        max_allowed = min(request.max_agents, self.policy.max_agents)
        available = [
            a for a in self._agents.values()
            if a.availability and a.health in (AgentHealthState.AVAILABLE, AgentHealthState.DEGRADED)
        ]

        # Match capabilities
        selected: List[Agent] = []
        for agent in available:
            if len(selected) >= max_allowed:
                break
            # Check if agent has required capabilities
            req_set = set(request.required_capabilities)
            agent_cap_set = set(agent.capabilities)
            if req_set.issubset(agent_cap_set) or not req_set:
                selected.append(agent)

        fallback = [a for a in available if a not in selected]

        reason = (
            f"Selected {len(selected)} agent(s) matching capabilities {request.required_capabilities} "
            f"under policy max_agents={max_allowed}."
        )

        return AgentSelectionResult(
            selected_agents=selected,
            selection_reason=reason,
            fallback_agents=fallback
        )
