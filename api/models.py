"""
LLMorch Phase 9 — API response models.
These are typed Pydantic models derived from the internal schemas,
safe for exposure over the API boundary (no raw secrets, no internal blobs by default).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ─── Pagination ───────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[Any]


# ─── Runs / Tasks ─────────────────────────────────────────────────────────────

class RunSummary(BaseModel):
    run_id: str
    task_id: str
    agent_id: str
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    exit_status: Optional[int] = None
    failure_reason: Optional[str] = None


class TaskSummary(BaseModel):
    task_id: str
    workflow_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    objective: str
    status: str
    assigned_agent_id: Optional[str] = None
    retry_count: int = 0
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskDetail(TaskSummary):
    inputs: Any = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    preferred_roles: List[str] = Field(default_factory=list)
    risk_level: str = "LOW"
    runs: List[RunSummary] = Field(default_factory=list)


# ─── Agents ───────────────────────────────────────────────────────────────────

class AgentSummary(BaseModel):
    agent_id: str
    provider: str
    interface: str
    capabilities: List[str] = Field(default_factory=list)
    health: str = "UNKNOWN"
    role: str = "general_analysis"
    status: str = "ACTIVE"
    enabled: bool = True
    current_model_id: Optional[str] = None
    supported_models: List[str] = Field(default_factory=list)
    current_task_id: Optional[str] = None
    current_task_objective: Optional[str] = None
    tokens_used: int = 0
    token_limit: Optional[int] = None
    tokens_remaining: Optional[int] = None
    failover_count: int = 0
    switch_count: int = 0
    executable: bool = True
    execution_disabled_reason: Optional[str] = None
    registered_at: Optional[datetime] = None



# ─── Events ───────────────────────────────────────────────────────────────────

class EventEnvelope(BaseModel):
    event_id: str
    event_type: str
    timestamp: datetime
    run_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    sequence: int = 0
    payload: Dict[str, Any] = Field(default_factory=dict)


# ─── Findings ─────────────────────────────────────────────────────────────────

class FindingSummary(BaseModel):
    finding_id: str
    task_id: Optional[str] = None
    hypothesis: Optional[str] = None
    state: str = "OPEN"
    severity: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class FindingDetail(FindingSummary):
    evidence_ids: List[str] = Field(default_factory=list)
    artifact_ids: List[str] = Field(default_factory=list)
    affected_locations: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: Optional[float] = None
    notes: Optional[str] = None


# ─── Evidence ─────────────────────────────────────────────────────────────────

class EvidenceSummary(BaseModel):
    evidence_id: str
    finding_id: Optional[str] = None
    task_id: Optional[str] = None
    source_tool: Optional[str] = None
    timestamp: Optional[datetime] = None
    raw_hash: Optional[str] = None
    canonical_hash: Optional[str] = None
    semantic_identity: Optional[str] = None


class EvidenceDetail(EvidenceSummary):
    tool_version: Optional[str] = None
    command: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    exit_code: Optional[int] = None
    sandbox_id: Optional[str] = None
    environment_fingerprint: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)


# ─── Checkpoints ──────────────────────────────────────────────────────────────

class CheckpointSummary(BaseModel):
    checkpoint_id: str
    task_id: str
    run_id: str
    stage: str
    created_at: Optional[datetime] = None


# ─── Analysis Units ───────────────────────────────────────────────────────────

class AnalysisUnitSummary(BaseModel):
    unit_id: str
    name: str
    unit_type: str
    domain: str
    priority: str
    snapshot_id: Optional[str] = None
    component_path: Optional[str] = None
    security_critical: bool = False


class AnalysisUnitDetail(AnalysisUnitSummary):
    description: Optional[str] = None
    rationale: Optional[str] = None
    entry_points: List[str] = Field(default_factory=list)
    relevant_files: List[str] = Field(default_factory=list)
    relevant_symbols: List[str] = Field(default_factory=list)
    security_properties: List[str] = Field(default_factory=list)
    attack_paths: List[Dict[str, Any]] = Field(default_factory=list)


# ─── Repository / Snapshots ───────────────────────────────────────────────────

class SnapshotSummary(BaseModel):
    snapshot_id: str
    repo_path: str
    commit_hash: Optional[str] = None
    branch: Optional[str] = None
    tag: Optional[str] = None
    created_at: Optional[datetime] = None
    total_files: int = 0
    family: Optional[str] = None


# ─── Security Surface ─────────────────────────────────────────────────────────

class SecuritySurfaceSummary(BaseModel):
    surface_id: str
    unit_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    entry_point_count: int = 0
    asset_count: int = 0
    boundary_count: int = 0
    attacker_capability_count: int = 0
    countermeasure_count: int = 0


# ─── Validation ───────────────────────────────────────────────────────────────

class ValidationSummary(BaseModel):
    validation_id: str
    finding_id: Optional[str] = None
    reproducer_id: Optional[str] = None
    verdict: str  # CONFIRMED / REJECTED / INCONCLUSIVE
    validator_name: Optional[str] = None
    timestamp: Optional[datetime] = None
    replay_count: int = 0
    determinism: Optional[str] = None


# ─── Reproducer ───────────────────────────────────────────────────────────────

class ReproducerSummary(BaseModel):
    reproducer_id: str
    finding_id: Optional[str] = None
    candidate_id: Optional[str] = None
    status: str
    manifest_hash: Optional[str] = None
    created_at: Optional[datetime] = None


# ─── Timeline ─────────────────────────────────────────────────────────────────

class TimelineEntry(BaseModel):
    event_id: str
    event_type: str
    timestamp: datetime
    actor: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    summary: str = ""
    run_id: Optional[str] = None
    task_id: Optional[str] = None


# ─── Controls ─────────────────────────────────────────────────────────────────

class ControlRequest(BaseModel):
    action: str  # pause | resume | cancel | retry | rerun_validation | approve
    target_type: str  # task | run | reproducer | validation
    target_id: str
    reason: Optional[str] = None
    session_token: Optional[str] = None


class ControlResponse(BaseModel):
    accepted: bool
    event_id: Optional[str] = None
    message: str
    control_plane_decision: str  # ACCEPTED | REJECTED | PENDING_APPROVAL


# ─── Session ──────────────────────────────────────────────────────────────────

class SessionInfo(BaseModel):
    session_id: str
    created_at: datetime
    role: str = "analyst"


# ─── Realtime event (WS push) ─────────────────────────────────────────────────

class RealtimeEvent(BaseModel):
    event_id: str
    event_type: str
    timestamp: datetime
    sequence: int
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


# ─── Feedback ─────────────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    finding_id: str
    label: str  # CONFIRMED | FALSE_POSITIVE | MISSED_VULNERABILITY | etc.
    comment: Optional[str] = None
    session_token: Optional[str] = None


class FeedbackResponse(BaseModel):
    accepted: bool
    feedback_id: Optional[str] = None
    message: str


# ─── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "9.1.0"
    db_connected: bool = True
    realtime_active: bool = True


# ─── Phase 9.1: Models ────────────────────────────────────────────────────────

class ModelSummary(BaseModel):
    model_id: str
    provider: str
    display_name: str
    context_window: int
    max_output_tokens: int
    input_token_tracking_supported: bool = True
    output_token_tracking_supported: bool = True
    token_estimation_method: str = "LOCAL_TOKENIZER"
    capabilities: List[str] = Field(default_factory=list)
    enabled: bool = True
    cost_per_million_input: float = 0.0
    cost_per_million_output: float = 0.0


class ModelDetail(ModelSummary):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


# ─── Phase 9.1: Switching ─────────────────────────────────────────────────────

class AgentSwitchRequest(BaseModel):
    task_id: str
    new_agent_id: str
    reason: str
    resume_action: str = "RESUME_FROM_CHECKPOINT"  # RESUME_FROM_CHECKPOINT | RETRY | PAUSE
    new_model_id: Optional[str] = None
    session_token: Optional[str] = None


class AgentSwitchResponse(BaseModel):
    accepted: bool
    switch_id: Optional[str] = None
    task_id: str
    previous_agent_id: str
    new_agent_id: str
    new_model_id: Optional[str] = None
    new_run_id: Optional[str] = None
    checkpoint_id: Optional[str] = None
    resume_action: str
    message: str


class ModelSwitchRequest(BaseModel):
    agent_id: str
    new_model_id: str
    reason: str
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    scope: str = "CURRENT_TASK"  # CURRENT_TASK | FUTURE_TASKS | GLOBAL
    session_token: Optional[str] = None


class ModelSwitchResponse(BaseModel):
    accepted: bool
    switch_id: Optional[str] = None
    agent_id: str
    previous_model_id: str
    new_model_id: str
    scope: str
    message: str


class SwitchAuditRecord(BaseModel):
    switch_id: str
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    previous_agent_id: Optional[str] = None
    new_agent_id: Optional[str] = None
    previous_model_id: Optional[str] = None
    new_model_id: Optional[str] = None
    switch_type: str = "MANUAL"
    reason: str = ""
    checkpoint_id: Optional[str] = None
    resume_action: Optional[str] = None
    status: str = "COMPLETED"
    created_at: Optional[datetime] = None


# ─── Phase 9.1: Tokens & Budgets ──────────────────────────────────────────────

class TokenUsageRecordResponse(BaseModel):
    record_id: str
    run_id: str
    task_id: str
    attempt_id: Optional[str] = None
    agent_id: str
    model_id: str
    stage: str
    input_tokens_actual: int = 0
    output_tokens_actual: int = 0
    total_tokens_actual: int = 0
    input_tokens_estimated: int = 0
    output_tokens_estimated: int = 0
    total_tokens_estimated: int = 0
    input_source: str = "UNKNOWN"
    output_source: str = "UNKNOWN"
    token_source: str = "UNKNOWN"
    is_estimated: bool = False
    token_limit: Optional[int] = None
    tokens_remaining: Optional[int] = None
    created_at: Optional[datetime] = None


class TokenSummaryResponse(BaseModel):
    total_tokens_actual: int = 0
    total_tokens_estimated: int = 0
    effective_total_tokens: int = 0
    input_tokens_actual: int = 0
    output_tokens_actual: int = 0
    input_tokens_estimated: int = 0
    output_tokens_estimated: int = 0
    token_budget: int = 500000
    tokens_remaining: int = 500000
    status: str = "AVAILABLE"  # AVAILABLE | LOW | NEAR_LIMIT | EXHAUSTED | BLOCKED
    estimated_work_remaining: int = 0
    by_agent: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    by_model: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    by_stage: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    top_tasks: List[Dict[str, Any]] = Field(default_factory=list)


class TokenBudgetUpdateRequest(BaseModel):
    scope_type: str = "run"  # run | agent | model | task | phase
    scope_id: str = "default"
    budget_limit: int = 150000
    budget_limit_tokens: Optional[int] = None
    warning_threshold_pct: Optional[float] = 0.8
    exhaustion_threshold_pct: Optional[float] = 0.95
    run_id: Optional[str] = None
    session_token: Optional[str] = None

    def model_post_init(self, __context):
        if self.budget_limit_tokens is not None:
            self.budget_limit = self.budget_limit_tokens


# ─── Phase 9.1: Repository Token Estimation ───────────────────────────────────

class EstimateCostRequest(BaseModel):
    repository_path: Optional[str] = None
    repo_path: Optional[str] = None
    analysis_policy: Optional[str] = "BALANCED"
    selected_models: List[str] = Field(default_factory=list)
    session_token: Optional[str] = None

    def model_post_init(self, __context):
        if not self.repository_path and self.repo_path:
            self.repository_path = self.repo_path
        elif not self.repo_path and self.repository_path:
            self.repo_path = self.repository_path
        if not self.repository_path:
            self.repository_path = "."
            self.repo_path = "."


class EstimateCostResponse(BaseModel):
    estimate_id: str
    repository_path: str
    snapshot_id: Optional[str] = None
    total_files_discovered: int
    source_files_count: int
    security_relevant_files_count: int
    excluded_files_count: int
    quarantined_secrets_count: int
    raw_token_estimate: int
    llm_scoped_token_estimate: int
    analysis_unit_estimate: int
    context_expansion_estimate: int
    initial_analysis_estimate: int
    followup_analysis_estimate: int
    estimated_total_tokens: int
    recommended_budget: int
    estimation_method: str
    confidence: str
    confidence_rationale: str
    breakdown_by_language: List[Dict[str, Any]] = Field(default_factory=list)
    breakdown_by_stage: List[Dict[str, Any]] = Field(default_factory=list)
    secrets_excluded_safely: bool = True
    created_at: Optional[datetime] = None


# ─── Phase 9.1: Settings & Config ─────────────────────────────────────────────

class SettingsResponse(BaseModel):
    settings_id: str = "global-settings"
    version: int = 1
    agents: Dict[str, Any] = Field(default_factory=dict)
    models: Dict[str, Any] = Field(default_factory=dict)
    tokens: Dict[str, Any] = Field(default_factory=dict)
    scope: Dict[str, Any] = Field(default_factory=dict)
    execution: Dict[str, Any] = Field(default_factory=dict)
    security: Dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[datetime] = None


class SettingsUpdateRequest(BaseModel):
    agents: Optional[Dict[str, Any]] = None
    models: Optional[Dict[str, Any]] = None
    tokens: Optional[Dict[str, Any]] = None
    scope: Optional[Dict[str, Any]] = None
    execution: Optional[Dict[str, Any]] = None
    session_token: Optional[str] = None
