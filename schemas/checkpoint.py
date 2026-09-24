"""
LLMorch Data Contracts - Checkpoint Model
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid


class Checkpoint(BaseModel):
    """
    Execution state snapshot allowing a task to be resumed by a new agent
    without relying on context/conversation history of the prior agent.
    """
    checkpoint_id: str = Field(default_factory=lambda: f"chk-{uuid.uuid4().hex[:12]}", description="Unique checkpoint identifier")
    task_id: str = Field(..., description="Target task identifier")
    workflow_id: Optional[str] = Field(default=None, description="Workflow identifier if part of a workflow")
    run_id: Optional[str] = Field(default=None, description="Run attempt identifier that produced checkpoint")
    completed_subtasks: List[str] = Field(default_factory=list, description="Subtasks successfully completed")
    remaining_subtasks: List[str] = Field(default_factory=list, description="Subtasks remaining to execute")
    task_state: Dict[str, Any] = Field(default_factory=dict, description="Structured intermediate task execution state")
    artifact_refs: List[str] = Field(default_factory=list, description="References to produced artifacts")
    evidence_refs: List[str] = Field(default_factory=list, description="References to recorded evidence items")
    finding_refs: List[str] = Field(default_factory=list, description="References to generated security findings")
    hypothesis_refs: List[str] = Field(default_factory=list, description="References to active research hypotheses")
    workspace_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Workspace state snapshot details")
    repository_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Git commit / file tree snapshot details")
    next_action: Optional[str] = Field(default=None, description="Explicit next recommended action or entrypoint")
    recovery_context: Dict[str, Any] = Field(default_factory=dict, description="Context regarding failure and recovery state")
    is_valid: bool = Field(default=True, description="Whether checkpoint is valid for resume")
    invalidation_reason: Optional[str] = Field(default=None, description="Reason if checkpoint is stale or invalid")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Checkpoint creation timestamp")
