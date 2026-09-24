"""
LLMorch Data Contracts - Phase 8 Independent Validation Model
Defines contracts for determinism probing, independent minimization verification,
semantic replay comparison, and authoritative validator verdicts.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid

from schemas.candidate import Candidate
from schemas.reproducer import Reproducer


class DeterminismClass(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    FLAKY = "FLAKY"
    VARIABLE = "VARIABLE"
    NON_REPRODUCING = "NON_REPRODUCING"
    UNKNOWN = "UNKNOWN"


class DeterminismResult(BaseModel):
    """Result of multi-pass determinism probing."""
    determinism_class: DeterminismClass
    replay_count: int
    success_count: int
    failure_count: int
    failure_rate: float
    fingerprint_set: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class MinimizationResult(BaseModel):
    """Result of reproducer/stimulus minimization and independent validator verification."""
    original_hash: str
    minimized_hash: str
    original_size: int
    minimized_size: int
    reduction_percentage: float
    reproduction_verified_by_validator: bool = False
    retained_artifact_hash: str = ""


class ReplayComparison(BaseModel):
    """Comparison across primary validation run and subsequent replay runs."""
    primary_run_id: str
    replay_run_ids: List[str] = Field(default_factory=list)
    raw_match: bool = False
    canonical_match: bool = False
    semantic_match: bool = False
    observed_failure_signal: str = ""
    match_policy: str = "semantic"
    tolerances: Dict[str, Any] = Field(default_factory=dict)


class ValidationVerdict(str, Enum):
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class EnvironmentManifest(BaseModel):
    """Captured host and tool environment context for deterministic replay."""
    os_name: str = "Linux"
    architecture: str = "x86_64"
    python_version: str = ""
    tool_versions: Dict[str, str] = Field(default_factory=dict)
    environment_fingerprint: str = ""


class ValidationRequest(BaseModel):
    """Request submitted to the Independent Validator."""
    request_id: str = Field(default_factory=lambda: f"vreq-{uuid.uuid4().hex[:12]}")
    candidate: Candidate
    reproducer: Reproducer
    repo_root: str
    requested_replay_count: int = 3
    expected_signal: Optional[str] = None


class ValidationResult(BaseModel):
    """
    Authoritative Verdict emitted solely by the Independent Validator.
    Never created by LLM or Reproducer Generation Engine.
    """
    validation_id: str = Field(default_factory=lambda: f"val-{uuid.uuid4().hex[:12]}")
    candidate_id: str
    reproducer_id: str
    verdict: ValidationVerdict
    confidence_score: float = Field(ge=0.0, le=1.0)
    determinism: DeterminismResult
    replay_comparison: ReplayComparison
    minimization: Optional[MinimizationResult] = None
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    execution_trace_ids: List[str] = Field(default_factory=list)
    reasoning: str = Field(..., description="Explainable technical rationale backed by evidence")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
