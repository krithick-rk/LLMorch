"""
LLMorch Data Contracts - Event Model
"""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class EventType(str, Enum):
    """Structured event type classification."""
    TASK_CREATED = "TASK_CREATED"
    TASK_DISPATCHED = "TASK_DISPATCHED"
    AGENT_SELECTED = "AGENT_SELECTED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_OUTPUT = "AGENT_OUTPUT"
    TOOL_STARTED = "TOOL_STARTED"
    TOOL_FINISHED = "TOOL_FINISHED"
    ARTIFACT_CREATED = "ARTIFACT_CREATED"
    EVIDENCE_RECORDED = "EVIDENCE_RECORDED"
    CHECKPOINT_CREATED = "CHECKPOINT_CREATED"
    AGENT_FAILED = "AGENT_FAILED"
    AGENT_UNAVAILABLE = "AGENT_UNAVAILABLE"
    TASK_REASSIGNED = "TASK_REASSIGNED"
    TASK_RESUMED = "TASK_RESUMED"
    TASK_COMPLETED = "TASK_COMPLETED"
    STATE_TRANSITION = "STATE_TRANSITION"
    # Phase 4 Strategy Events
    STRATEGY_EVALUATION_STARTED = "STRATEGY_EVALUATION_STARTED"
    STRATEGY_DECISION_CREATED = "STRATEGY_DECISION_CREATED"
    AGENT_CANDIDATES_RESOLVED = "AGENT_CANDIDATES_RESOLVED"
    AGENT_COUNT_SELECTED = "AGENT_COUNT_SELECTED"
    AGENT_ROLE_ASSIGNED = "AGENT_ROLE_ASSIGNED"
    STRATEGY_ESCALATION_TRIGGERED = "STRATEGY_ESCALATION_TRIGGERED"
    STRATEGY_STOPPED = "STRATEGY_STOPPED"
    # Phase 5 Failover & Recovery Events
    AGENT_FAILURE_DETECTED = "AGENT_FAILURE_DETECTED"
    AGENT_QUOTA_EXHAUSTED = "AGENT_QUOTA_EXHAUSTED"
    AGENT_TIMEOUT = "AGENT_TIMEOUT"
    AGENT_MARKED_UNAVAILABLE = "AGENT_MARKED_UNAVAILABLE"
    AGENT_HEALTH_CHANGED = "AGENT_HEALTH_CHANGED"
    FAILOVER_STARTED = "FAILOVER_STARTED"
    REPLACEMENT_CANDIDATES_RESOLVED = "REPLACEMENT_CANDIDATES_RESOLVED"
    REPLACEMENT_AGENT_SELECTED = "REPLACEMENT_AGENT_SELECTED"
    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"
    RECOVERY_BLOCKED = "RECOVERY_BLOCKED"
    RECOVERY_EXHAUSTED = "RECOVERY_EXHAUSTED"
    # Phase 6 Cross-Project Memory Events
    MEMORY_RETRIEVAL_STARTED = "MEMORY_RETRIEVAL_STARTED"
    MEMORY_MATCH_FOUND = "MEMORY_MATCH_FOUND"
    MEMORY_PATTERN_APPLICABILITY_CHECKED = "MEMORY_PATTERN_APPLICABILITY_CHECKED"
    MEMORY_PROMOTION_PROPOSED = "MEMORY_PROMOTION_PROPOSED"
    MEMORY_PROMOTION_ACCEPTED = "MEMORY_PROMOTION_ACCEPTED"
    MEMORY_PROMOTION_REJECTED = "MEMORY_PROMOTION_REJECTED"
    MEMORY_PATTERN_MERGED = "MEMORY_PATTERN_MERGED"
    MEMORY_PATTERN_REJECTED = "MEMORY_PATTERN_REJECTED"
    MEMORY_ACCESS_BLOCKED = "MEMORY_ACCESS_BLOCKED"
    # Phase 7 Repository Intelligence Events
    REPOSITORY_SCAN_STARTED = "REPOSITORY_SCAN_STARTED"
    REPOSITORY_SCAN_COMPLETED = "REPOSITORY_SCAN_COMPLETED"
    FILE_CLASSIFIED = "FILE_CLASSIFIED"
    BUILD_TARGET_DISCOVERED = "BUILD_TARGET_DISCOVERED"
    SYMLINK_BLOCKED = "SYMLINK_BLOCKED"
    SECRET_QUARANTINED = "SECRET_QUARANTINED"
    DEPENDENCY_DISCOVERED = "DEPENDENCY_DISCOVERED"
    REACHABILITY_COMPUTED = "REACHABILITY_COMPUTED"
    SECURITY_SURFACE_CREATED = "SECURITY_SURFACE_CREATED"
    ANALYSIS_UNIT_CREATED = "ANALYSIS_UNIT_CREATED"
    ANALYSIS_UNIT_RANKED = "ANALYSIS_UNIT_RANKED"
    CONTEXT_EXPANSION_REQUESTED = "CONTEXT_EXPANSION_REQUESTED"
    CONTEXT_EXPANSION_ALLOWED = "CONTEXT_EXPANSION_ALLOWED"
    CONTEXT_EXPANSION_BLOCKED = "CONTEXT_EXPANSION_BLOCKED"


class Event(BaseModel):
    """
    Append-only structured audit event model.
    Provides verifiable lineage across execution.
    """
    event_id: str = Field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:12]}", description="Unique event identifier")
    run_id: Optional[str] = Field(default=None, description="Associated run attempt identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event occurrence timestamp")
    event_type: EventType = Field(..., description="Categorized event type")
    actor: str = Field(..., description="Identity of actor that triggered event")
    tool: Optional[str] = Field(default=None, description="Associated tool identifier if applicable")
    payload_ref: Optional[str] = Field(default=None, description="Reference URI/path to large event payload")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Inline structured event payload")
    parent_event_id: Optional[str] = Field(default=None, description="Causal parent event identifier")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
