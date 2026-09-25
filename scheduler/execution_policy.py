"""
LLMorch Development & Runtime Execution Policy (Phase 9.1).
Defines administrative control over which agents are permitted to execute real subprocesses.

Decouples registration from execution:
- Registered: Agent exists in registry, schemas, UI, model mappings.
- Executable: Agent is permitted to spawn real processes under the active execution policy.

In this environment:
- Antigravity / AGY: ENABLED & EXECUTABLE
- Codex CLI: ENABLED & EXECUTABLE
- Claude Code: REGISTERED & CONFIGURED, but REAL EXECUTION DISABLED (Development execution policy)
"""

from __future__ import annotations

import os
from typing import Dict, Any, List, Set, Optional
from schemas.errors import AgentExecutionDisabled, LLMorchError, ErrorCode


class ExecutionPolicy:
    """
    Administrative Execution Policy Manager.
    Enforces which registered agents are permitted to execute real tasks.
    """

    def __init__(
        self,
        enabled_agents: Optional[List[str]] = None,
        disabled_agents: Optional[List[str]] = None,
        allow_real_claude_execution: bool = False,
        allow_real_agy_execution: bool = True,
        allow_real_codex_execution: bool = True,
        allow_mock_execution: bool = True,
    ):
        # Default policy: AGY & Codex enabled, Claude registered but disabled
        self.enabled_agents: Set[str] = set(
            enabled_agents if enabled_agents is not None else ["agent-agy-01", "agent-codex-01", "agent-fourth-01", "agent-mock-04"]
        )
        self.disabled_agents: Set[str] = set(
            disabled_agents if disabled_agents is not None else ["agent-claude-01"]
        )
        # Explicit real execution guards
        self.allow_real_claude_execution: bool = allow_real_claude_execution
        self.allow_real_agy_execution: bool = allow_real_agy_execution
        self.allow_real_codex_execution: bool = allow_real_codex_execution
        self.allow_mock_execution: bool = allow_mock_execution

    def is_agent_executable(self, agent_id: str, adapter: Optional[Any] = None) -> bool:
        """
        Returns True if the agent is permitted to execute under the active policy.
        """
        if adapter is not None:
            if getattr(adapter, "is_mock", False) or adapter.__class__.__name__ in ("ContractClaudeAdapter", "MockClaudeAdapter", "ControlledMockAdapter"):
                return True

        if agent_id in self.disabled_agents:
            return False
        if "claude" in agent_id.lower() and not self.allow_real_claude_execution:
            return False
        if "agy" in agent_id.lower() and not self.allow_real_agy_execution:
            return False
        if "codex" in agent_id.lower() and not self.allow_real_codex_execution:
            return False
        return agent_id in self.enabled_agents or self.allow_mock_execution


    def get_agent_disabled_reason(self, agent_id: str) -> Optional[str]:
        if "claude" in agent_id.lower() and not self.allow_real_claude_execution:
            return "Development execution policy: Claude Code real execution is disabled"
        if agent_id in self.disabled_agents:
            return f"Agent '{agent_id}' is administratively disabled in execution policy"
        return None

    def assert_can_execute(self, agent_id: str) -> None:
        """
        Throws AgentExecutionDisabled if the agent is not executable.
        Must be called prior to spawning any process.
        """
        if not self.is_agent_executable(agent_id):
            reason = self.get_agent_disabled_reason(agent_id) or "Agent execution disabled by policy"
            raise AgentExecutionDisabled(
                f"Execution denied for agent '{agent_id}': {reason}. "
                "The agent remains registered and configured, but execution is disabled.",
                details={"agent_id": agent_id, "reason": reason}
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled_agents": sorted(list(self.enabled_agents)),
            "disabled_agents": sorted(list(self.disabled_agents)),
            "allow_real_claude_execution": self.allow_real_claude_execution,
            "allow_real_agy_execution": self.allow_real_agy_execution,
            "allow_real_codex_execution": self.allow_real_codex_execution,
            "allow_mock_execution": self.allow_mock_execution,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionPolicy:
        return cls(
            enabled_agents=data.get("enabled_agents"),
            disabled_agents=data.get("disabled_agents"),
            allow_real_claude_execution=data.get("allow_real_claude_execution", False),
            allow_real_agy_execution=data.get("allow_real_agy_execution", True),
            allow_real_codex_execution=data.get("allow_real_codex_execution", True),
            allow_mock_execution=data.get("allow_mock_execution", True),
        )


# Global policy instance
_GLOBAL_POLICY: ExecutionPolicy = ExecutionPolicy()


def get_execution_policy() -> ExecutionPolicy:
    return _GLOBAL_POLICY


def set_execution_policy(policy: ExecutionPolicy) -> None:
    global _GLOBAL_POLICY
    _GLOBAL_POLICY = policy
