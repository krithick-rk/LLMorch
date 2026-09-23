"""
LLMorch Data Contracts - Task Model
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class RiskLevel(str, Enum):
    """Task execution risk classification."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskStatus(str, Enum):
    """Task state machine states."""
    QUEUED = "QUEUED"
    DISPATCHED = "DISPATCHED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    BLOCKED = "BLOCKED"


class TaskWorkspacePolicy(BaseModel):
    """Workspace isolation and access rules for a task."""
    isolated: bool = Field(default=True, description="Whether to execute in an isolated sandbox")
    read_only_root: bool = Field(default=False, description="Whether the repository root is mounted read-only")
    allowed_paths: List[str] = Field(default_factory=list, description="Explicitly allowed subdirectories/files")
    allow_network: bool = Field(default=False, description="Whether network egress is permitted")


class TaskToolPolicy(BaseModel):
    """Tool execution permissions for a task."""
    allowed_tools: List[str] = Field(default_factory=list, description="Whitelisted tool identifiers")
    blocked_tools: List[str] = Field(default_factory=list, description="Explicitly forbidden tool identifiers")
    require_approval_for: List[str] = Field(default_factory=list, description="Tools requiring manual approval")


class TaskBudget(BaseModel):
    """Resource budget constraints for a task."""
    max_steps: int = Field(default=50, description="Maximum execution steps permitted")
    max_seconds: int = Field(default=3600, description="Maximum execution time in seconds")
    max_cost_usd: Optional[float] = Field(default=None, description="Maximum spending limit in USD, if applicable")


class Task(BaseModel):
    """
    Durable unit of work in LLMorch.
    Must NOT contain provider-specific assumptions.
    """
    task_id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex[:12]}", description="Unique durable task identifier")
    workflow_id: Optional[str] = Field(default=None, description="Parent workflow identifier")
    parent_task_id: Optional[str] = Field(default=None, description="Parent task identifier for subtasks")
    objective: str = Field(..., description="Clear, provider-neutral objective description")
    inputs: List[Dict[str, Any]] = Field(default_factory=list, description="Inputs and parameters for the task")
    dependencies: List[str] = Field(default_factory=list, description="List of task_ids that must complete first")
    required_capabilities: List[str] = Field(default_factory=list, description="Required agent capabilities")
    preferred_roles: List[str] = Field(default_factory=list, description="Preferred functional agent roles")
    risk_level: RiskLevel = Field(default=RiskLevel.MEDIUM, description="Assigned risk level")
    workspace_policy: TaskWorkspacePolicy = Field(default_factory=TaskWorkspacePolicy, description="Workspace access rules")
    tool_policy: TaskToolPolicy = Field(default_factory=TaskToolPolicy, description="Tool execution rules")
    budget: TaskBudget = Field(default_factory=TaskBudget, description="Execution budget limits")
    status: TaskStatus = Field(default=TaskStatus.QUEUED, description="Current state machine status")
    assigned_agent_id: Optional[str] = Field(default=None, description="Currently assigned agent identifier")
    retry_count: int = Field(default=0, description="Number of retry attempts executed so far")
    acceptance_criteria: List[str] = Field(default_factory=list, description="Verifiable success conditions")
    result_ref: Optional[str] = Field(default=None, description="Reference URI/path to final task result artifact")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Task creation timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Task execution start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Task completion/termination timestamp")
