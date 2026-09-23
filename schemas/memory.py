"""
LLMorch Data Contracts - Phase 6 Memory System Schemas
Defines strongly typed contracts for PatternRecord, ProjectMemoryRecord, GlobalMemoryRecord,
ResearchStrategyRecord, ResearchOutcomeRecord, MemoryRetrievalRecord, and MemoryPromotionRecord.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class PatternDomain(str, Enum):
    """Supported vulnerability / analysis pattern domain categories."""
    C_CPP = "c_cpp"
    GO = "go"
    JAVA = "java"
    PYTHON = "python"
    RTL = "rtl"
    HW_SW = "hw_sw"
    GENERIC = "generic"


class MemoryConfidence(str, Enum):
    """Confidence lifecycle states for research memory records."""
    PROPOSED = "PROPOSED"
    SUPPORTED = "SUPPORTED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    DEPRECATED = "DEPRECATED"


class MemoryPrivacyClass(str, Enum):
    """Privacy classification for memory records to prevent raw project data leakage."""
    PROJECT_PRIVATE = "PROJECT_PRIVATE"
    GLOBAL_GENERALIZED = "GLOBAL_GENERALIZED"
    SENSITIVE = "SENSITIVE"
    RESTRICTED = "RESTRICTED"


class MatchType(str, Enum):
    """Retrieval match classification types."""
    EXACT = "EXACT"
    STRUCTURAL = "STRUCTURAL"
    FEATURE = "FEATURE"
    SEMANTIC = "SEMANTIC"


class ApplicabilityStatus(str, Enum):
    """LLM applicability verification status."""
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNCERTAIN = "UNCERTAIN"


class PatternRecord(BaseModel):
    """
    First-class strongly typed record representing a generalized research pattern.
    Must contain NO raw source code, repository paths, secrets, or project-specific IDs.
    """
    pattern_id: str = Field(default_factory=lambda: f"pat-{uuid.uuid4().hex[:12]}", description="Unique pattern identifier")
    domain: PatternDomain = Field(default=PatternDomain.GENERIC, description="Target domain classification")
    title: str = Field(..., description="Abstract human-readable summary title")
    structural_signature: str = Field(..., description="Normalized structural hash/signature of pattern")
    semantic_signature: str = Field(..., description="Abstract semantic pattern description")
    indicators: List[str] = Field(default_factory=list, description="Key structural or semantic indicators")
    affected_constructs: List[str] = Field(default_factory=list, description="Architectural or code constructs affected")
    supporting_evidence_types: List[str] = Field(default_factory=list, description="Types of evidence supporting pattern")
    successful_analysis_steps: List[str] = Field(default_factory=list, description="Analysis steps that successfully identified pattern")
    rejected_analysis_steps: List[str] = Field(default_factory=list, description="Analysis steps that produced false positives or failed")
    validation_method: Optional[str] = Field(default=None, description="Recommended validation method (e.g. formal, dynamic, unit_test)")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Metadata explaining pattern origin without leaking secrets")
    confidence_state: MemoryConfidence = Field(default=MemoryConfidence.PROPOSED, description="Confidence lifecycle state")
    privacy_class: MemoryPrivacyClass = Field(default=MemoryPrivacyClass.GLOBAL_GENERALIZED, description="Privacy classification")
    observation_count: int = Field(default=1, description="Number of times pattern has been observed across projects")
    version: int = Field(default=1, description="Pattern schema / evolution version")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Record last update timestamp")


class ProjectMemoryRecord(BaseModel):
    """
    Repository-scoped memory record.
    May reference project-specific paths, facts, local hypotheses, and local findings.
    """
    record_id: str = Field(default_factory=lambda: f"pm-rec-{uuid.uuid4().hex[:12]}", description="Unique project memory record ID")
    project_id: str = Field(..., description="Repository / project identifier")
    task_id: Optional[str] = Field(default=None, description="Associated task ID")
    run_id: Optional[str] = Field(default=None, description="Associated run ID")
    domain: PatternDomain = Field(default=PatternDomain.GENERIC, description="Domain classification")
    architecture_facts: List[str] = Field(default_factory=list, description="Local architectural observations")
    local_findings: List[Dict[str, Any]] = Field(default_factory=list, description="Local vulnerability findings")
    rejected_hypotheses: List[Dict[str, Any]] = Field(default_factory=list, description="Local rejected hypotheses")
    successful_strategies: List[str] = Field(default_factory=list, description="Successful local analysis strategies")
    failed_strategies: List[str] = Field(default_factory=list, description="Failed local analysis strategies")
    evidence_refs: List[str] = Field(default_factory=list, description="References to project evidence")
    privacy_class: MemoryPrivacyClass = Field(default=MemoryPrivacyClass.PROJECT_PRIVATE, description="Always PROJECT_PRIVATE")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")


class ResearchStrategyRecord(BaseModel):
    """
    Persisted record of an analysis strategy and its historical outcome.
    """
    strategy_id: str = Field(default_factory=lambda: f"strat-{uuid.uuid4().hex[:12]}", description="Unique strategy record ID")
    domain: PatternDomain = Field(default=PatternDomain.GENERIC, description="Target domain classification")
    name: str = Field(..., description="Strategy name or title")
    steps: List[str] = Field(default_factory=list, description="Ordered analysis steps")
    outcome: MemoryConfidence = Field(..., description="Outcome state (VALIDATED, REJECTED, etc.)")
    relevant_conditions: List[str] = Field(default_factory=list, description="Conditions where strategy applies")
    notes: Optional[str] = Field(default=None, description="Cautionary notes or findings summary")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")


class ResearchOutcomeRecord(BaseModel):
    """
    Structured outcome produced at the conclusion of an investigation workflow task.
    Acts as the bridge from execution to project/global memory.
    """
    outcome_id: str = Field(default_factory=lambda: f"out-{uuid.uuid4().hex[:12]}", description="Unique outcome record ID")
    project_id: str = Field(..., description="Target repository ID")
    task_id: str = Field(..., description="Task ID")
    run_id: str = Field(..., description="Run ID")
    domain: PatternDomain = Field(default=PatternDomain.GENERIC, description="Domain classification")
    analysis_unit_id: Optional[str] = Field(default=None, description="Scoped analysis unit ID")
    hypothesis: str = Field(..., description="Research hypothesis evaluated")
    confidence: MemoryConfidence = Field(..., description="Final outcome confidence")
    successful_steps: List[str] = Field(default_factory=list)
    rejected_steps: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    is_generalizable: bool = Field(default=False, description="Flag indicating candidate for global promotion")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MemoryRetrievalRecord(BaseModel):
    """
    Result returned by the memory retrieval engine for a target query.
    """
    pattern_id: str = Field(..., description="ID of matched PatternRecord")
    match_type: MatchType = Field(..., description="Match classification (EXACT, STRUCTURAL, FEATURE, SEMANTIC)")
    match_score: float = Field(..., description="Match score between 0.0 and 1.0")
    matched_features: List[str] = Field(default_factory=list, description="List of matching features/indicators")
    pattern: PatternRecord = Field(..., description="Retrieved generalized pattern record")
    confidence_state: MemoryConfidence = Field(..., description="Confidence state of matched pattern")
    reason: str = Field(..., description="Human-readable explanation of why pattern matched")


class MemoryPromotionRecord(BaseModel):
    """
    Audit record capturing a promotion decision from project memory to global research memory.
    """
    promotion_id: str = Field(default_factory=lambda: f"prom-{uuid.uuid4().hex[:12]}", description="Unique promotion ID")
    project_id: str = Field(..., description="Source project ID")
    outcome_id: str = Field(..., description="Source outcome ID")
    pattern_id: Optional[str] = Field(default=None, description="Generated or updated global PatternRecord ID")
    accepted: bool = Field(..., description="Whether promotion was accepted")
    rejection_reason: Optional[str] = Field(default=None, description="Reason for rejection if denied")
    sanitized_fields: List[str] = Field(default_factory=list, description="Fields that were sanitized or stripped")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LLMApplicabilityResult(BaseModel):
    """
    Structured response from LLM applicability verification step.
    Does NOT declare code vulnerable — only determines if pattern warrants investigation.
    """
    pattern_id: str = Field(..., description="Pattern ID being evaluated")
    status: ApplicabilityStatus = Field(..., description="Applicability status (APPLICABLE, NOT_APPLICABLE, UNCERTAIN)")
    reasoning_summary: str = Field(..., description="Explanation of applicability check")
    required_evidence: List[str] = Field(default_factory=list, description="Suggested evidence needed to validate")
    suggested_next_actions: List[str] = Field(default_factory=list, description="Next steps for analysis")
