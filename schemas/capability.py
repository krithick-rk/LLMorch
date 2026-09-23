"""
LLMorch Data Contracts - Capability Model
"""

from enum import Enum
from typing import List
from pydantic import BaseModel, Field


class AgentCapability(str, Enum):
    """Data-driven capabilities supported by LLMorch agents."""
    REPOSITORY_ANALYSIS = "repository_analysis"
    CODE_ANALYSIS = "code_analysis"
    RTL_ANALYSIS = "rtl_analysis"
    SOFTWARE_ANALYSIS = "software_analysis"
    DEBUGGING = "debugging"
    SHELL_EXECUTION = "shell_execution"
    TEST_GENERATION = "test_generation"
    REPRODUCER_GENERATION = "reproducer_generation"
    STATIC_ANALYSIS = "static_analysis"
    FORMAL_ANALYSIS = "formal_analysis"
    DOCUMENTATION_ANALYSIS = "documentation_analysis"
    SECURITY_REVIEW = "security_review"


class CapabilityRequirements(BaseModel):
    """Specification of required and optional capabilities for a task."""
    required: List[AgentCapability] = Field(default_factory=list, description="Must-have capabilities")
    preferred: List[AgentCapability] = Field(default_factory=list, description="Nice-to-have capabilities")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
