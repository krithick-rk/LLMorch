"""
LLMorch Data Contracts - Model & Model Registry Models (Phase 9.1)
Distinguishes Agent, Model, Provider, Adapter, Capability, and Task.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ModelCapability(str, Enum):
    """Fine-grained capability tags for models."""
    CODE_ANALYSIS = "code_analysis"
    DEEP_REASONING = "deep_reasoning"
    RTL_ANALYSIS = "rtl_analysis"
    SOFTWARE_SECURITY = "software_security"
    FAST_TRIAGE = "fast_triage"
    REPOSITORY_MAPPING = "repository_mapping"
    REPRODUCER_GENERATION = "reproducer_generation"
    SYNTAX_VERIFICATION = "syntax_verification"
    STRUCTURED_OUTPUT = "structured_output"
    LONG_CONTEXT = "long_context"


class TokenEstimationMethod(str, Enum):
    """Method used for estimating token consumption."""
    ACTUAL_TOKENIZER = "ACTUAL_TOKENIZER"
    LOCAL_TOKENIZER = "LOCAL_TOKENIZER"
    HEURISTIC_ESTIMATE = "HEURISTIC_ESTIMATE"
    PROVIDER_REPORTED = "PROVIDER_REPORTED"


class ModelSelectionMode(str, Enum):
    """Mode for choosing a model."""
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    POLICY = "POLICY"


class ModelPolicy(str, Enum):
    """Predefined policies that resolve to model selection configuration."""
    BALANCED = "BALANCED"
    DEEP_ANALYSIS = "DEEP_ANALYSIS"
    LOW_TOKEN = "LOW_TOKEN"
    FAST_TRIAGE = "FAST_TRIAGE"
    REPOSITORY_MAPPING = "REPOSITORY_MAPPING"
    RTL_SECURITY = "RTL_SECURITY"
    SOFTWARE_SECURITY = "SOFTWARE_SECURITY"


class Model(BaseModel):
    """
    Representation of an LLM model in LLMorch.
    Distinct from Agent and Provider.
    """
    model_id: str = Field(..., description="Unique model identifier (e.g. claude-3-7-sonnet-20250219, gpt-4o, agy-deep-research)")
    provider: str = Field(..., description="Provider identity (e.g. anthropic, openai, antigravity, auxiliary)")
    display_name: str = Field(..., description="Human-readable model name")
    context_window: int = Field(default=128000, description="Maximum total context window size in tokens")
    max_output_tokens: int = Field(default=8192, description="Maximum completion tokens")
    input_token_tracking_supported: bool = Field(default=True, description="Whether exact input token tracking is reported")
    output_token_tracking_supported: bool = Field(default=True, description="Whether exact output token tracking is reported")
    token_estimation_method: TokenEstimationMethod = Field(default=TokenEstimationMethod.LOCAL_TOKENIZER, description="Default token estimation method")
    capabilities: List[str] = Field(default_factory=list, description="Model-specific capability tags")
    enabled: bool = Field(default=True, description="Whether model is enabled for selection")
    cost_per_million_input: float = Field(default=0.0, description="Reference cost per 1M input tokens (accounting only)")
    cost_per_million_output: float = Field(default=0.0, description="Reference cost per 1M output tokens (accounting only)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary extension metadata")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")


class ModelSelectionRequest(BaseModel):
    """Input payload for model selection engine."""
    agent_id: Optional[str] = None
    task_type: Optional[str] = None
    programming_language: Optional[str] = None
    repository_family: Optional[str] = None
    task_complexity: str = "medium"  # low, medium, high, critical
    required_context_size: int = 16000
    remaining_token_budget: Optional[int] = None
    required_capabilities: List[str] = Field(default_factory=list)
    mode: ModelSelectionMode = ModelSelectionMode.AUTO
    policy: Optional[ModelPolicy] = None
    preferred_model_id: Optional[str] = None


class ModelSelectionResult(BaseModel):
    """Result of model selection engine."""
    selected_model: Model
    agent_id: Optional[str] = None
    selection_mode: ModelSelectionMode
    selection_reason: str
    fallback_models: List[str] = Field(default_factory=list)
    confidence: float = 1.0
