"""
LLMorch Data Contracts - Agent Policy Contract
"""

from pydantic import BaseModel, Field, field_validator


class AgentPolicy(BaseModel):
    """
    Dynamic 1-4 Agent Policy Configuration.
    Supports single-agent, 2-agent, 3-agent, and 4-agent modes dynamically.
    """
    min_agents: int = Field(default=1, ge=1, le=4, description="Minimum allowed active agents")
    max_agents: int = Field(default=4, ge=1, le=4, description="Maximum allowed active agents (1 to 4)")
    adaptive: bool = Field(default=True, description="Whether agent count scales dynamically based on load/task complexity")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")

    @field_validator("max_agents")
    def validate_max_agents(cls, v, values):
        if "min_agents" in values.data and v < values.data["min_agents"]:
            raise ValueError("max_agents cannot be less than min_agents")
        return v
