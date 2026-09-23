"""
LLMorch Data Contracts - Agent Selection Contract
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .agent import Agent
from .health import AgentHealthState


class AgentSelectionRequest(BaseModel):
    """Input payload requesting agent assignment from Orchestrator/Registry."""
    required_capabilities: List[str] = Field(default_factory=list, description="Must-have capabilities")
    preferred_roles: List[str] = Field(default_factory=list, description="Preferred functional roles")
    risk_level: str = Field(default="MEDIUM", description="Task risk level")
    minimum_health: AgentHealthState = Field(default=AgentHealthState.AVAILABLE, description="Minimum health requirement")
    workspace_requirements: Dict[str, Any] = Field(default_factory=dict, description="Workspace constraints")
    tool_requirements: List[str] = Field(default_factory=list, description="Required tool support")
    budget: Dict[str, Any] = Field(default_factory=dict, description="Task budget constraints")
    max_agents: int = Field(default=4, ge=1, le=4, description="Maximum agents to assign (1 to 4)")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")


class AgentSelectionResult(BaseModel):
    """Response payload containing assigned agents and rationale."""
    selected_agents: List[Agent] = Field(default_factory=list, description="List of assigned Agent instances")
    selection_reason: str = Field(..., description="Justification and rationale for agent selection")
    fallback_agents: List[Agent] = Field(default_factory=list, description="Secondary agents available if primary fails")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
