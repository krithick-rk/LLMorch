"""
LLMorch Data Contracts - Configuration & Settings (Phase 9.1)
Authoritative persistent analyst configuration data models.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from schemas.model import ModelSelectionMode, ModelPolicy
from schemas.token import TokenBudgetConfig


class AgentSettings(BaseModel):
    """Analyst configuration for agents."""
    enabled_agents: List[str] = Field(
        default_factory=lambda: ["agent-agy-01", "agent-claude-01", "agent-codex-01", "agent-fourth-01"]
    )
    preferred_agent: str = "agent-agy-01"
    fallback_agents: List[str] = Field(
        default_factory=lambda: ["agent-codex-01", "agent-fourth-01", "agent-claude-01"]
    )
    max_concurrent_agents: int = 4
    allow_agent_switching: bool = True
    auto_failover: bool = True


class ModelSettings(BaseModel):
    """Analyst configuration for models."""
    selection_mode: ModelSelectionMode = ModelSelectionMode.AUTO
    preferred_model: str = "runtime-resolved"
    fallback_model: str = "runtime-resolved"
    policy: ModelPolicy = ModelPolicy.BALANCED
    context_preference: int = 32000
    allow_model_switching: bool = True


class ScopeSettings(BaseModel):
    """Analyst configuration for repository analysis scope."""
    include_paths: List[str] = Field(default_factory=list)
    exclude_paths: List[str] = Field(
        default_factory=lambda: [
            "vendor/", "third_party/", "node_modules/", ".git/", "build/", "dist/",
            "target/", ".cache/", "__pycache__/"
        ]
    )
    languages: List[str] = Field(default_factory=list)
    include_generated_code: bool = False
    include_vendor_code: bool = False
    include_build_output: bool = False
    quarantine_secrets: bool = True


class ExecutionSettings(BaseModel):
    """Analyst configuration for execution runtime."""
    concurrency: int = 2
    timeout_seconds: int = 3600
    retry_limit: int = 3
    sandbox_policy: str = "process"
    high_impact_approval_required: bool = True
    require_approval_near_budget: bool = True
    context_expansion_limit: int = 5


class SecuritySettings(BaseModel):
    """Security status and masked credentials metadata. Never contains plain secrets."""
    credentials_status: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "anthropic": {"configured": True, "masked": "sk-ant••••••••", "status": "CONNECTED"},
            "openai": {"configured": True, "masked": "sk-proj••••••••", "status": "CONNECTED"},
            "antigravity": {"configured": True, "masked": "agy-••••••••", "status": "CONNECTED"},
        }
    )
    egress_filter_active: bool = True
    isolated_workspaces: bool = True


class SystemSettings(BaseModel):
    """Complete analyst configuration state for LLMorch."""
    settings_id: str = "global-settings"
    version: int = 1
    agents: AgentSettings = Field(default_factory=AgentSettings)
    models: ModelSettings = Field(default_factory=ModelSettings)
    tokens: TokenBudgetConfig = Field(default_factory=TokenBudgetConfig)
    scope: ScopeSettings = Field(default_factory=ScopeSettings)
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
