"""
LLMorch Data Contracts - Repository Token Estimation (Phase 9.1)
Structured cost, size, and token footprint estimates before LLM dispatch.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field


class EstimationMethod(str, Enum):
    """Method used for repository token estimation."""
    ACTUAL_TOKENIZER = "ACTUAL_TOKENIZER"
    LOCAL_TOKENIZER = "LOCAL_TOKENIZER"
    HEURISTIC_ESTIMATE = "HEURISTIC_ESTIMATE"


class ConfidenceLevel(str, Enum):
    """Confidence level in the estimation output."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class LanguageTokenEstimate(BaseModel):
    """Token footprint breakdown by programming language or file type."""
    language: str
    file_count: int
    raw_bytes: int
    estimated_tokens: int
    llm_eligible_tokens: int
    excluded_tokens: int


class StageTokenEstimate(BaseModel):
    """Expected token consumption per pipeline stage."""
    stage: str
    display_name: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_total_tokens: int
    description: str


class RepositoryTokenEstimate(BaseModel):
    """
    Authoritative estimate of repository analysis token consumption.
    Produced before expensive LLM analysis begins.
    """
    estimate_id: str = Field(default_factory=lambda: f"est-{uuid.uuid4().hex[:12]}", description="Unique estimate id")
    repository_path: str = Field(..., description="Target repository path")
    snapshot_id: Optional[str] = Field(default=None, description="Snapshot reference if generated")

    # File counts
    total_files_discovered: int = 0
    source_files_count: int = 0
    security_relevant_files_count: int = 0
    excluded_files_count: int = 0
    quarantined_secrets_count: int = 0

    # Byte sizes
    raw_repository_bytes: int = 0
    relevant_source_bytes: int = 0
    llm_eligible_bytes: int = 0
    excluded_bytes: int = 0

    # Token Estimates
    raw_token_estimate: int = 0                  # Entire repo footprint
    llm_scoped_token_estimate: int = 0           # Only security-relevant/eligible source
    analysis_unit_estimate: int = 0              # Tokens across generated AnalysisUnits
    context_expansion_estimate: int = 0          # Expected dynamic context expansion
    initial_analysis_estimate: int = 0           # Initial sweep (intake + discovery + AU ranking)
    followup_analysis_estimate: int = 0          # Follow-up deep investigation & reproduction
    estimated_total_tokens: int = 0              # Expected total consumption
    recommended_budget: int = 0                  # Recommended budget with safety margin (e.g. 20-30%)

    # Method & Confidence
    estimation_method: EstimationMethod = EstimationMethod.LOCAL_TOKENIZER
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    confidence_rationale: str = ""

    # Detailed breakdowns
    breakdown_by_language: List[LanguageTokenEstimate] = Field(default_factory=list)
    breakdown_by_stage: List[StageTokenEstimate] = Field(default_factory=list)
    sample_files_analyzed: int = 0
    secrets_excluded_safely: bool = True

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of estimate generation")
    schema_version: str = Field(default="1.0.0", description="Contract version")
