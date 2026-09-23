"""
LLMorch Data Contracts - Task Result Model
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class TaskResult(BaseModel):
    """
    Normalized result schema returned by agent adapters after execution.
    """
    task_id: str = Field(..., description="Target task identifier")
    run_id: str = Field(..., description="Run attempt identifier")
    status: str = Field(..., description="Normalized status string (SUCCEEDED, FAILED, UNRESOLVED)")
    hypothesis: Optional[str] = Field(default=None, description="Extracted vulnerability hypothesis statement")
    affected_locations: List[Dict[str, Any]] = Field(default_factory=list, description="Target source code/RTL locations")
    evidence_refs: List[str] = Field(default_factory=list, description="Associated evidence item IDs")
    artifact_refs: List[str] = Field(default_factory=list, description="Associated artifact IDs")
    attack_preconditions: List[str] = Field(default_factory=list, description="Preconditions required for exploitation")
    contradictions: List[str] = Field(default_factory=list, description="Observed contradictions or counter-evidence")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Normalized agent confidence rating (0.0 to 1.0)")
    recommended_next_task: Optional[str] = Field(default=None, description="Suggested follow-up investigation task")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Execution metrics (duration, tool calls, token usage)")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
