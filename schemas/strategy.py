"""
LLMorch Data Contracts - Phase 4 Strategy & Agent Assignment Models
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class StrategyDecision(BaseModel):
    """
    Machine-readable explainability contract for adaptive agent count & selection decisions.
    Answers: Why this many agents? Why these agents? What signals drove the selection?
    """
    decision_id: str = Field(default_factory=lambda: f"strat-{uuid.uuid4().hex[:12]}")
    task_id: str = Field(..., description="Target task identifier")
    chosen_agent_count: int = Field(..., ge=1, le=4, description="Selected number of agents (1-4)")
    selected_agents: List[str] = Field(default_factory=list, description="IDs of chosen agents")
    candidate_agents: List[str] = Field(default_factory=list, description="IDs of eligible candidates considered")
    excluded_agents: List[str] = Field(default_factory=list, description="IDs of candidates excluded due to hard constraints")
    required_capabilities: List[str] = Field(default_factory=list, description="Capabilities derived from task analysis")
    estimated_complexity: str = Field(default="MEDIUM", description="Task complexity signal (LOW, MEDIUM, HIGH, CRITICAL)")
    estimated_parallelism: str = Field(default="MODERATE", description="Parallelism potential (LOW, MODERATE, HIGH)")
    estimated_uncertainty: str = Field(default="MEDIUM", description="Task uncertainty signal (LOW, MEDIUM, HIGH)")
    security_sensitivity: str = Field(default="MEDIUM", description="Security sensitivity signal (LOW, MEDIUM, HIGH)")
    budget_available: float = Field(default=100.0, description="Allocated budget units")
    estimated_cost: float = Field(default=1.0, description="Estimated resource/cost impact")
    reason: List[str] = Field(default_factory=list, description="Human-readable rationale for selection")
    expected_benefit: str = Field(default="Balanced coverage", description="Expected outcome benefit of selection")
    escalation_conditions: List[str] = Field(default_factory=list, description="Triggers for adding another agent")
    stop_conditions: List[str] = Field(default_factory=list, description="Triggers for halting agent pool expansion")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentAssignment(BaseModel):
    """
    Contract for assigning task-time roles to selected agents.
    """
    assignment_id: str = Field(default_factory=lambda: f"assign-{uuid.uuid4().hex[:12]}")
    strategy_decision_id: str = Field(..., description="Parent StrategyDecision identifier")
    task_id: str = Field(..., description="Target task identifier")
    agent_id: str = Field(..., description="Assigned agent identifier")
    role: str = Field(..., description="Task-time role assignment (primary_investigation, independent_investigation, etc.)")
    required_capabilities: List[str] = Field(default_factory=list)
    assignment_reason: str = Field(default="Capability match and pool availability")
    workspace_id: Optional[str] = Field(default=None)
    context_policy: Dict[str, Any] = Field(default_factory=dict)
