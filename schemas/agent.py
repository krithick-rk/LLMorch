"""
LLMorch Data Contracts - Agent Model
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .health import AgentHealthState, AgentUsageStatus, AgentQuotaStatus


class AgentInterface(str, Enum):
    """Interface transport protocol used to communicate with the agent."""
    CLI = "cli"
    API = "api"
    A2A = "a2a"
    EMBEDDED = "embedded"


class Agent(BaseModel):
    """
    Representation of an agent instance in LLMorch.
    agent_id is independent from provider/model identity.
    """
    agent_id: str = Field(..., description="Unique independent agent instance identifier (e.g. agent-agy-01)")
    provider: str = Field(..., description="Provider name (e.g. antigravity, claude, codex, opencode)")
    interface: AgentInterface = Field(default=AgentInterface.CLI, description="Interface mechanism")
    model: str = Field(default="runtime-resolved", description="Model identity or alias (runtime-resolved if dynamic)")
    capabilities: List[str] = Field(default_factory=list, description="Data-driven capability tags")
    protocols: List[str] = Field(default_factory=list, description="Supported protocol versions (e.g. cli-v1, mcp-v1)")
    permissions: List[str] = Field(default_factory=list, description="Permission scopes granted to agent")
    health: AgentHealthState = Field(default=AgentHealthState.AVAILABLE, description="Current health status")
    availability: bool = Field(default=True, description="Whether the agent is currently available for dispatch")
    concurrency_limit: int = Field(default=1, description="Maximum concurrent tasks this agent can execute")
    usage_status: AgentUsageStatus = Field(default_factory=AgentUsageStatus, description="Real-time quota and usage metrics")
    quota_status: AgentQuotaStatus = Field(default=AgentQuotaStatus.UNKNOWN, description="Quota classification status")
    workspace_class: str = Field(default="standard", description="Workspace isolation level required")
    auth_profile: Dict[str, Any] = Field(default_factory=dict, description="Authentication profile reference metadata")
    adapter_version: str = Field(default="1.0.0", description="Version of the adapter bound to this agent")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary extension metadata")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
