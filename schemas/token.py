"""
LLMorch Data Contracts - Token Accounting & Budgeting (Phase 9.1)
Authoritative token tracking across agents, models, tasks, runs, and analysis stages.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field


class TokenSource(str, Enum):
    """Source provenance for reported token values."""
    PROVIDER_REPORTED = "PROVIDER_REPORTED"
    CLI_REPORTED = "CLI_REPORTED"
    LOCAL_TOKENIZER = "LOCAL_TOKENIZER"
    HEURISTIC_ESTIMATE = "HEURISTIC_ESTIMATE"
    UNKNOWN = "UNKNOWN"


class TokenLimitStatus(str, Enum):
    """State classification for token budget consumption."""
    AVAILABLE = "AVAILABLE"        # > 30% remaining
    LOW = "LOW"                    # < 30% remaining
    NEAR_LIMIT = "NEAR_LIMIT"      # < 10% remaining
    EXHAUSTED = "EXHAUSTED"        # 0 remaining or limit exceeded
    BLOCKED = "BLOCKED"            # Exceeded with blocking policy


class TokenUsageRecord(BaseModel):
    """
    Append-only persistent token accounting record.
    Never overwrites historical usage.
    """
    record_id: str = Field(default_factory=lambda: f"tok-{uuid.uuid4().hex[:12]}", description="Unique token record id")
    run_id: str = Field(..., description="Associated run attempt id")
    task_id: str = Field(..., description="Associated task id")
    attempt_id: Optional[str] = Field(default=None, description="Task attempt or retry id")
    agent_id: str = Field(..., description="Agent that incurred the token usage")
    model_id: str = Field(..., description="Model that incurred the token usage")
    stage: str = Field(default="investigation", description="Pipeline stage (e.g. discovery, intake, static_analysis, deep_analysis, reproducer, validation)")

    # Actual telemetry (from provider/CLI)
    input_tokens_actual: int = Field(default=0, description="Actual input tokens reported by provider/CLI")
    output_tokens_actual: int = Field(default=0, description="Actual output tokens reported by provider/CLI")
    total_tokens_actual: int = Field(default=0, description="Actual total tokens reported")

    # Estimated telemetry (from local tokenizer or heuristic)
    input_tokens_estimated: int = Field(default=0, description="Estimated input tokens")
    output_tokens_estimated: int = Field(default=0, description="Estimated output tokens")
    total_tokens_estimated: int = Field(default=0, description="Estimated total tokens")

    # Metadata & provenance
    input_source: TokenSource = Field(default=TokenSource.UNKNOWN, description="Source of input token count")
    output_source: TokenSource = Field(default=TokenSource.UNKNOWN, description="Source of output token count")
    token_source: TokenSource = Field(default=TokenSource.UNKNOWN, description="Overall telemetry source")
    is_estimated: bool = Field(default=False, description="Flag indicating if the primary reported count is estimated")

    token_limit: Optional[int] = Field(default=None, description="Task or run limit at time of record")
    tokens_remaining: Optional[int] = Field(default=None, description="Tokens remaining in budget at time of record")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of record")
    schema_version: str = Field(default="1.0.0", description="Schema version")


class TokenBudgetConfig(BaseModel):
    """Configurable token limits and thresholds."""
    run_budget: int = Field(default=500000, description="Global run token budget ceiling")
    initial_analysis_budget: int = Field(default=150000, description="Budget allocated for initial repo intake & discovery")
    agent_limits: Dict[str, int] = Field(
        default_factory=lambda: {
            "agent-agy-01": 150000,
            "agent-claude-01": 100000,
            "agent-codex-01": 120000,
            "agent-fourth-01": 80000,
        },
        description="Per-agent token budget ceilings"
    )
    model_limits: Dict[str, int] = Field(default_factory=dict, description="Optional per-model budget ceilings")
    task_limit_default: int = Field(default=40000, description="Default token budget per task")
    phase_budgets: Dict[str, int] = Field(
        default_factory=lambda: {
            "discovery": 50000,
            "static_analysis": 100000,
            "deep_analysis": 150000,
            "reproduction": 75000,
            "validation": 50000,
        },
        description="Stage/phase allocated budgets"
    )
    low_threshold_percent: float = Field(default=30.0, description="Percentage remaining threshold for LOW warning")
    near_limit_threshold_percent: float = Field(default=10.0, description="Percentage remaining threshold for NEAR_LIMIT warning")
    action_on_exhausted: str = Field(default="switch_or_pause", description="Action when budget exhausted: pause | switch | request_approval | fail")


class TokenAccountingSummary(BaseModel):
    """Aggregate token usage metrics for observability."""
    total_tokens_actual: int = 0
    total_tokens_estimated: int = 0
    effective_total_tokens: int = 0
    input_tokens_actual: int = 0
    output_tokens_actual: int = 0
    input_tokens_estimated: int = 0
    output_tokens_estimated: int = 0
    token_budget: int = 500000
    tokens_remaining: int = 500000
    status: TokenLimitStatus = TokenLimitStatus.AVAILABLE
    estimated_work_remaining: int = 0
    by_agent: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    by_model: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    by_stage: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    top_tasks: List[Dict[str, Any]] = Field(default_factory=list)
