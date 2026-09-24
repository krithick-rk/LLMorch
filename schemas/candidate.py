"""
LLMorch Data Contracts - Phase 8 Candidate Model
Represents an investigated security hypothesis that may warrant reproduction.
Does not constitute a confirmed finding until independently verified by the Validator.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid


class CandidatePriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Candidate(BaseModel):
    """
    Candidate hypothesis model for reproducer generation and independent validation.
    Maintains provenance back to discovering agent run and analysis unit.
    """
    candidate_id: str = Field(default_factory=lambda: f"cand-{uuid.uuid4().hex[:12]}", description="Unique candidate ID")
    task_id: str = Field(..., description="Originating task ID")
    run_id: str = Field(..., description="Originating run ID")
    analysis_unit_id: Optional[str] = Field(default=None, description="Associated analysis unit ID")
    hypothesis_id: str = Field(default_factory=lambda: f"hypo-{uuid.uuid4().hex[:8]}", description="Hypothesis identifier")
    domain: str = Field(default="software", description="Domain: c, rust, python, rtl, formal, hw_sw")
    security_property: str = Field(..., description="Security property being checked (e.g. memory_safety, access_control)")
    attack_surface: str = Field(default="", description="Target attack surface or entry point")
    attack_path: str = Field(default="", description="Suspected attack path")
    expected_behavior: str = Field(..., description="Expected safe behavior")
    suspected_behavior: str = Field(..., description="Suspected vulnerability manifestation")
    required_evidence: List[str] = Field(default_factory=list, description="Evidence types required to confirm")
    source_references: List[Dict[str, Any]] = Field(default_factory=list, description="Grounded source file references")
    tool_observations: List[Dict[str, Any]] = Field(default_factory=list, description="Pre-check or static tool observations")
    memory_references: List[str] = Field(default_factory=list, description="Global memory pattern IDs informing hypothesis")
    historical_references: List[str] = Field(default_factory=list, description="Historical outcome or prior finding references")
    priority: CandidatePriority = Field(default=CandidatePriority.MEDIUM, description="Investigation priority")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Candidate creation timestamp")
