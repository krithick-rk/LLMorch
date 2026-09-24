"""
LLMorch Data Contracts - Phase 7 Analysis Unit Model
Representing the smallest meaningful security analysis boundary in a repository.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid


class AnalysisUnitType(str, Enum):
    """Scope granularity of an analysis unit."""
    FILE = "FILE"
    MODULE = "MODULE"
    FUNCTION = "FUNCTION"
    RTL_BLOCK = "RTL_BLOCK"
    INTERFACE = "INTERFACE"
    SUBSYSTEM = "SUBSYSTEM"
    BAZEL_TARGET = "BAZEL_TARGET"
    HW_SW_CONTRACT = "HW_SW_CONTRACT"


class PriorityLevel(str, Enum):
    """Analysis priority level (investigation resource allocation score)."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    IGNORE = "IGNORE"


class AnalysisUnit(BaseModel):
    """
    First-class AnalysisUnit model.
    Represents the smallest meaningful security context provided to agents.
    Prevents sending raw entire repositories to agents.
    """
    analysis_unit_id: str = Field(default_factory=lambda: f"au-{uuid.uuid4().hex[:12]}")
    repository_id: str = Field(..., description="Parent repository identifier")
    snapshot_id: str = Field(..., description="Associated repository snapshot ID")
    unit_type: AnalysisUnitType = Field(default=AnalysisUnitType.MODULE)
    domain: str = Field(default="generic", description="Language/domain (rtl, c_cpp, go, java, python, hw_sw)")
    name: str = Field(..., description="Human-readable name of AnalysisUnit")
    description: str = Field(default="", description="Summary description of security scope")
    anchors: List[str] = Field(default_factory=list, description="Core entry points or symbol names")
    source_files: List[str] = Field(default_factory=list, description="Primary source file paths")
    symbols: List[str] = Field(default_factory=list, description="Associated symbol IDs")
    build_targets: List[str] = Field(default_factory=list, description="Associated build target IDs")
    modules: List[str] = Field(default_factory=list, description="Contained module/package names")
    dependencies: List[str] = Field(default_factory=list, description="Dependent AnalysisUnit or file IDs")
    entry_points: List[str] = Field(default_factory=list, description="External entry point functions or ports")
    assets: List[str] = Field(default_factory=list, description="Sensitive assets or registers protected")
    trust_boundaries: List[str] = Field(default_factory=list, description="Crossed trust boundaries")
    security_properties: List[str] = Field(default_factory=list, description="Invariants or security requirements")
    countermeasures: List[str] = Field(default_factory=list, description="Known countermeasures present")
    reachable_components: List[str] = Field(default_factory=list, description="Reachable downstream components")
    relevance_score: float = Field(default=0.0, description="Transparent relevance rank score (0.0 - 1.0)")
    priority: PriorityLevel = Field(default=PriorityLevel.MEDIUM)
    classification: str = Field(default="PRIMARY_SOURCE")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Generator provenance and rules")
    included_context: List[str] = Field(default_factory=list, description="Files/symbols included in context")
    excluded_context: List[str] = Field(default_factory=list, description="Files/secrets excluded from context")
    expansion_reason: Optional[str] = Field(default=None, description="Reason if context was expanded")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = Field(default="1.0.0")
