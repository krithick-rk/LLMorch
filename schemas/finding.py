"""
LLMorch Data Contracts - Finding Model
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class FindingState(str, Enum):
    """Lifecycle states of a security finding."""
    HYPOTHESIS = "HYPOTHESIS"
    REVIEWED = "REVIEWED"
    CORROBORATED = "CORROBORATED"
    CONTRADICTED = "CONTRADICTED"
    VALIDATION_PENDING = "VALIDATION_PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    UNRESOLVED = "UNRESOLVED"


class FindingLocation(BaseModel):
    """Specific code, file, or hardware structure location reference."""
    file_path: str = Field(..., description="File path relative to repository root")
    start_line: Optional[int] = Field(default=None, description="Starting line number")
    end_line: Optional[int] = Field(default=None, description="Ending line number")
    symbol: Optional[str] = Field(default=None, description="Function, module, or RTL signal name")
    context_snippet: Optional[str] = Field(default=None, description="Brief line snippet for context")


class Finding(BaseModel):
    """
    Representation of a security finding or vulnerability hypothesis.
    The orchestrator owns state transitions.
    """
    finding_id: str = Field(default_factory=lambda: f"fnd-{uuid.uuid4().hex[:12]}", description="Unique finding identifier")
    fingerprint: str = Field(..., description="Deduplication fingerprint hash based on location & vulnerability type")
    hypothesis: str = Field(..., description="Detailed vulnerability hypothesis statement")
    locations: List[FindingLocation] = Field(default_factory=list, description="Target source code or RTL locations")
    supporting_evidence: List[str] = Field(default_factory=list, description="List of supporting evidence_ids")
    contradicting_evidence: List[str] = Field(default_factory=list, description="List of contradicting evidence_ids")
    validation_method: Optional[str] = Field(default=None, description="Method used to validate (e.g. repro_script, formal_proof)")
    validator_result: Optional[Dict[str, Any]] = Field(default=None, description="Raw or parsed validator result payload")
    state: FindingState = Field(default=FindingState.HYPOTHESIS, description="Current lifecycle state owned by orchestrator")
    lineage: List[str] = Field(default_factory=list, description="Parent finding_ids or history of derivations")
    timestamps: Dict[str, datetime] = Field(
        default_factory=lambda: {"created_at": datetime.utcnow()},
        description="Audit timestamps (created_at, updated_at, validated_at, etc.)"
    )
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
