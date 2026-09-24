"""
LLMorch Agent Registry (Phase 9.1)
Manages agent registration, health state tracking, model association, and capability-driven selection.
Supports 1 to 4 configured agents dynamically with model routing and switch tracking.
"""

from typing import Dict, List, Optional, Any
from schemas.agent import Agent, AgentInterface
from schemas.health import AgentHealthState, AgentUsageStatus, AgentQuotaStatus
from schemas.agent_selection import AgentSelectionRequest, AgentSelectionResult
from schemas.policy import AgentPolicy
from schemas.errors import AgentUnavailableError, LLMorchError, ErrorCode
from registry.model_registry import ModelRegistry


class AgentRegistry:
    """
    Central Agent Registry for elastic agent management.
    Never hard-codes agent identity or fixed team roles.
    Integrates with ModelRegistry to separate agent execution boundaries from model intelligence.
    """

    def __init__(
        self,
        policy: Optional[AgentPolicy] = None,
        model_registry: Optional[ModelRegistry] = None,
        populate_defaults: bool = False
    ):
        self.policy = policy or AgentPolicy(min_agents=1, max_agents=4, adaptive=True)
        self.model_registry = model_registry or ModelRegistry()
        self._agents: Dict[str, Agent] = {}
        self._switch_counts: Dict[str, int] = {}
        self._failover_counts: Dict[str, int] = {}
        if populate_defaults:
            self.load_configured_agents()

    def load_configured_agents(self) -> None:
        """Discovers and registers agents configured in agents.yaml."""
        try:
            from configs.manager import ConfigManager
            configs = ConfigManager().get_agents_config()
            for cfg in configs:
                aid = cfg.get("id")
                if aid and aid not in self._agents:
                    iface = cfg.get("interface", "cli").lower()
                    agent = Agent(
                        agent_id=aid,
                        provider=cfg.get("provider", "unknown"),
                        interface=AgentInterface(iface) if iface in AgentInterface._value2member_map_ else AgentInterface.CLI,
                        capabilities=cfg.get("capabilities", []),
                        health=AgentHealthState.AVAILABLE,
                        availability=cfg.get("enabled", True),
                        concurrency_limit=cfg.get("concurrency_limit", 1),
                        role="general_analysis",
                        status="ACTIVE",
                        enabled=cfg.get("enabled", True),
                        adapter_version="1.0.0",
                    )
                    self.register_agent(agent)
        except Exception:
            pass

    def register_agent(self, agent: Agent) -> Agent:
        """Registers an agent instance in the registry and syncs supported models."""
        if not agent.supported_models and self.model_registry:
            models = self.model_registry.get_models_for_agent(agent.agent_id)
            agent.supported_models = [m.model_id for m in models]
            if not agent.current_model_id and agent.supported_models:
                default_m = self.model_registry.get_default_model_for_agent(agent.agent_id)
                agent.current_model_id = default_m.model_id if default_m else agent.supported_models[0]
                agent.model = agent.current_model_id

        self._agents[agent.agent_id] = agent
        if agent.agent_id not in self._switch_counts:
            self._switch_counts[agent.agent_id] = 0
        if agent.agent_id not in self._failover_counts:
            self._failover_counts[agent.agent_id] = 0
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
            agent.status = "BLOCKED" if health == AgentHealthState.QUOTA_LIMITED else "UNAVAILABLE"
        else:
            agent.availability = True
            if agent.status in ("UNAVAILABLE", "BLOCKED"):
                agent.status = "ACTIVE"
        return agent

    def set_agent_status(self, agent_id: str, status: str) -> Agent:
        """Updates operational status (ACTIVE, IDLE, DEGRADED, BLOCKED, SWITCHING, FAILOVER)."""
        agent = self.get_agent(agent_id)
        if not agent:
            raise AgentUnavailableError(f"Agent '{agent_id}' not found in registry")
        agent.status = status
        return agent

    def set_agent_enabled(self, agent_id: str, enabled: bool) -> Agent:
        """Enables or disables an agent from analyst control plane."""
        agent = self.get_agent(agent_id)
        if not agent:
            raise AgentUnavailableError(f"Agent '{agent_id}' not found in registry")
        agent.enabled = enabled
        agent.availability = enabled and (agent.health in (AgentHealthState.AVAILABLE, AgentHealthState.BUSY, AgentHealthState.DEGRADED))
        return agent

    def set_agent_model(self, agent_id: str, model_id: str) -> Agent:
        """Changes the active model for an agent, validating compatibility with ModelRegistry."""
        agent = self.get_agent(agent_id)
        if not agent:
            raise AgentUnavailableError(f"Agent '{agent_id}' not found in registry")

        if self.model_registry:
            if not self.model_registry.is_model_supported_by_agent(agent_id, model_id):
                supported = self.model_registry.get_models_for_agent(agent_id)
                supp_ids = [m.model_id for m in supported]
                raise LLMorchError(
                    f"Model '{model_id}' is not supported by agent '{agent_id}'. Supported: {supp_ids}",
                    code=ErrorCode.INVALID_STATE_TRANSITION
                )

        agent.current_model_id = model_id
        agent.model = model_id
        return agent

    def record_switch(self, agent_id: str) -> int:
        """Increments manual switch counter for agent."""
        curr = self._switch_counts.get(agent_id, 0) + 1
        self._switch_counts[agent_id] = curr
        return curr

    def record_failover(self, agent_id: str) -> int:
        """Increments failover counter for agent."""
        curr = self._failover_counts.get(agent_id, 0) + 1
        self._failover_counts[agent_id] = curr
        return curr

    def get_switch_count(self, agent_id: str) -> int:
        return self._switch_counts.get(agent_id, 0)

    def get_failover_count(self, agent_id: str) -> int:
        return self._failover_counts.get(agent_id, 0)

    def select_agents(self, request: AgentSelectionRequest) -> AgentSelectionResult:
        """
        Data-driven agent selection engine.
        Matches required capabilities and health requirements.
        Respects max_agents policy (1 to 4) and enabled flag.
        """
        max_allowed = min(request.max_agents, self.policy.max_agents)
        available = [
            a for a in self._agents.values()
            if a.availability
            and getattr(a, "enabled", True)
            and a.health in (AgentHealthState.AVAILABLE, AgentHealthState.DEGRADED)
            and getattr(a, "quota_status", None) != AgentQuotaStatus.EXHAUSTED
        ]

        # Match capabilities
        selected: List[Agent] = []
        for agent in available:
            if len(selected) >= max_allowed:
                break
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
