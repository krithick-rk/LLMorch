"""
LLMorch SoC Verification Core Typed Contracts
Defines authoritative data models for specifications, requirements, SoC components,
verification objectives, scenarios, tool plans, work packages, verification plans,
coverage items, gaps, policy candidates, and closure snapshots.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, model_validator

from schemas.soc_ontology import SoCBucket, BucketApplicability


class CostTier(str, Enum):
    LIGHTWEIGHT = "LIGHTWEIGHT"
    MODERATE = "MODERATE"
    EXPENSIVE = "EXPENSIVE"
    VERY_EXPENSIVE = "VERY_EXPENSIVE"


class ExecutionRecommendationMode(str, Enum):
    AUTO_EXECUTE = "AUTO_EXECUTE"
    RECOMMEND_EXECUTION = "RECOMMEND_EXECUTION"
    REQUIRE_REVIEW = "REQUIRE_REVIEW"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"


class PlanStatus(str, Enum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    SUPERSEDED = "SUPERSEDED"


class WorkPackageStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    QUEUED = "QUEUED"
    BLOCKED = "BLOCKED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class CoverageState(str, Enum):
    UNCOVERED = "UNCOVERED"
    PARTIAL = "PARTIAL"
    COVERED = "COVERED"
    WAIVED = "WAIVED"
    CONTRADICTORY = "CONTRADICTORY"


class GapSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PolicyStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    WAIVED = "WAIVED"
    REJECTED = "REJECTED"


class Specification(BaseModel):
    spec_id: str = Field(default_factory=lambda: f"spec-{uuid.uuid4().hex[:8]}")
    title: str
    document_type: str = "RM_TRM"  # RM_TRM, DATASHEET, REGISTER_SPEC, HEADER, SVD, MARKDOWN
    file_path: str
    revision: Optional[str] = "1.0"
    sections_count: int = 0
    requirements_extracted: int = 0
    extracted_claims: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    content_hash: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Requirement(BaseModel):
    requirement_id: str = Field(default_factory=lambda: f"req-{uuid.uuid4().hex[:8]}")
    spec_id: Optional[str] = None
    section: str = "General"
    title: str
    description: str
    primary_bucket: SoCBucket = SoCBucket.SECURITY
    affected_components: List[str] = Field(default_factory=list)
    is_security_critical: bool = True
    claims: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    provenance: str = "manual_or_extracted"
    status: str = "IDENTIFIED"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SoCComponent(BaseModel):
    component_id: str = Field(default_factory=lambda: f"comp-{uuid.uuid4().hex[:8]}")
    name: str
    component_type: str = "IP"  # IP, SUBSYSTEM, CPU_COMPLEX, INTERCONNECT, MEMORY, PERIPHERAL, SECURITY_BOUNDARY
    clock_domain: Optional[str] = None
    reset_domain: Optional[str] = None
    power_domain: Optional[str] = None
    security_tier: str = "STANDARD"  # PRIVILEGED, TRUSTZONE, STANDARD, UNTRUSTED
    source_files: List[str] = Field(default_factory=list)
    interfaces: List[str] = Field(default_factory=list)
    registers: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class InterfaceContract(BaseModel):
    contract_id: str = Field(default_factory=lambda: f"iface-{uuid.uuid4().hex[:8]}")
    source_component_id: str
    target_component_id: str
    interface_type: str = "BUS"  # BUS, IRQ, DMA, PIN, SIDEBAND, REGISTER, CLOCK, RESET, DEBUG, POWER
    signals: List[str] = Field(default_factory=list)
    clock_crossing: bool = False
    reset_crossing: bool = False
    security_boundary: bool = False
    notes: Optional[str] = None


class SecurityAsset(BaseModel):
    asset_id: str = Field(default_factory=lambda: f"asset-{uuid.uuid4().hex[:8]}")
    name: str
    asset_type: str  # KEY, SECRET, MEMORY_REGION, PRIVILEGE_STATE, LIFECYCLE_STATE, BOOT_ARTIFACT, DEBUG_PATH
    locations: List[str] = Field(default_factory=list)
    confidentiality: bool = True
    integrity: bool = True
    availability: bool = True
    threat_description: Optional[str] = None


class ThreatModel(BaseModel):
    threat_id: str = Field(default_factory=lambda: f"threat-{uuid.uuid4().hex[:8]}")
    title: str
    asset_id: Optional[str] = None
    actor: str = "Untrusted Software"  # Malicious SW, Physical Attacker, Debug Probe, DMA Master
    entry_point: str
    trust_boundary: str
    capability: str
    abuse_case: str
    assumptions: List[str] = Field(default_factory=list)
    mitigations: List[str] = Field(default_factory=list)


class VerificationObjective(BaseModel):
    objective_id: str = Field(default_factory=lambda: f"obj-{uuid.uuid4().hex[:8]}")
    requirement_id: Optional[str] = None
    bucket: SoCBucket
    title: str
    statement: str
    target_components: List[str] = Field(default_factory=list)
    verification_method: str = "SIMULATION"  # FORMAL, SIMULATION, STATIC_LINT, CDC_CHECK, SAST, EMULATION
    status: str = "PROPOSED"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VerificationScenario(BaseModel):
    scenario_id: str = Field(default_factory=lambda: f"scen-{uuid.uuid4().hex[:8]}")
    objective_id: str
    title: str
    stimulus: str
    preconditions: str
    expected_behavior: str
    target_components: List[str] = Field(default_factory=list)
    risk_rationale: str
    status: str = "PLANNED"


class TestIntent(BaseModel):
    test_id: str = Field(default_factory=lambda: f"test-{uuid.uuid4().hex[:8]}")
    scenario_id: str
    test_type: str = "COCOTB_SIMULATION"  # COCOTB_SIMULATION, VERILATOR_LINT, YOSYS_SYNTH, FORMAL_SVA
    inputs: Dict[str, Any] = Field(default_factory=dict)
    expected_observations: List[str] = Field(default_factory=list)
    harness_path: Optional[str] = None


class PropertyIntent(BaseModel):
    property_id: str = Field(default_factory=lambda: f"prop-{uuid.uuid4().hex[:8]}")
    objective_id: str
    property_expression: str
    assumptions: List[str] = Field(default_factory=list)
    proof_target: str
    is_bounded: bool = True
    bound_depth: int = 20


class ToolPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: f"tp-{uuid.uuid4().hex[:8]}")
    capability: str
    candidate_tools: List[str] = Field(default_factory=list)
    selected_tool: str
    execution_policy: str = "DETERMINISTIC_SANDBOX"
    expected_evidence_types: List[str] = Field(default_factory=list)
    budget_seconds: int = 300


class WorkPackage(BaseModel):
    project_id: Optional[str] = None
    package_id: str = Field(default_factory=lambda: f"wp-{uuid.uuid4().hex[:8]}")
    display_id: Optional[str] = None
    plan_id: str
    name: str
    description: str
    why_proposed: Optional[str] = None
    method: Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    agents: List[str] = Field(default_factory=list)
    expected_evidence: Optional[str] = None
    risks: List[str] = Field(default_factory=list)
    bucket: SoCBucket
    role: str
    objective_ids: List[str] = Field(default_factory=list)
    target_files: List[str] = Field(default_factory=list)
    supporting_context: List[str] = Field(default_factory=list)
    excluded_paths: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    estimated_tokens: int = 25000
    estimated_duration_seconds: int = 120
    cost_tier: CostTier = CostTier.MODERATE
    recommendation_mode: ExecutionRecommendationMode = ExecutionRecommendationMode.RECOMMEND_EXECUTION
    status: WorkPackageStatus = WorkPackageStatus.PROPOSED
    assigned_agent_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VerificationPlan(BaseModel):
    project_id: Optional[str] = None
    plan_id: str = Field(default_factory=lambda: f"vplan-{uuid.uuid4().hex[:8]}")
    display_id: Optional[str] = None
    version: int = 1
    repository_path: str
    repository_name: str
    scope_description: str
    target_scope: Optional[str] = None
    intent: Optional[str] = None
    why_files_selected: Optional[str] = None
    expected_output: Optional[str] = None
    status: PlanStatus = PlanStatus.DRAFT
    buckets_applicability: Dict[str, str] = Field(default_factory=dict)  # bucket -> APPLICABLE / NOT_APPLICABLE / UNKNOWN
    applicability_reasons: Dict[str, str] = Field(default_factory=dict)  # bucket -> explicit rationale string
    complexity_tier: Optional[str] = "MICRO"
    intent_depth: Optional[str] = "QUICK"
    repository_tokens: int = 0
    planning_tokens: int = 0
    execution_tokens: int = 0
    total_requirements: int = 0
    total_objectives: int = 0
    total_work_packages: int = 0
    total_estimated_tokens: int = 0
    total_estimated_duration_seconds: int = 0
    cost_tier: CostTier = CostTier.MODERATE
    recommendation_mode: ExecutionRecommendationMode = ExecutionRecommendationMode.RECOMMEND_EXECUTION
    replan_reason: Optional[str] = None
    parent_plan_id: Optional[str] = None
    author: Optional[str] = "Supervisor"
    objectives: List[Any] = Field(default_factory=list)
    work_packages: List[Any] = Field(default_factory=list)
    estimated_tokens: int = 0
    recommendation: Optional[str] = None
    rationale: Optional[str] = None
    created_by: str = "Supervisor"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None

    @model_validator(mode="after")
    def sync_aliases(self) -> VerificationPlan:
        if not self.estimated_tokens and self.total_estimated_tokens:
            self.estimated_tokens = self.total_estimated_tokens
        elif not self.total_estimated_tokens and self.estimated_tokens:
            self.total_estimated_tokens = self.estimated_tokens
        if not self.recommendation and self.recommendation_mode:
            self.recommendation = self.recommendation_mode.value if hasattr(self.recommendation_mode, "value") else str(self.recommendation_mode)
        return self


class CoverageItem(BaseModel):
    item_id: str = Field(default_factory=lambda: f"cov-{uuid.uuid4().hex[:8]}")
    plan_id: str
    bucket: SoCBucket
    requirement_id: Optional[str] = None
    objective_id: Optional[str] = None
    scenario_id: Optional[str] = None
    coverage_state: CoverageState = CoverageState.UNCOVERED
    evidence_ids: List[str] = Field(default_factory=list)
    waiver_reason: Optional[str] = None
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Gap(BaseModel):
    gap_id: str = Field(default_factory=lambda: f"gap-{uuid.uuid4().hex[:8]}")
    plan_id: str
    bucket: SoCBucket
    title: str
    description: str
    severity: GapSeverity = GapSeverity.MEDIUM
    requirement_id: Optional[str] = None
    recommended_action: str
    status: str = "OPEN"  # OPEN, RESOLVED, WAIVED
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PolicyCandidate(BaseModel):
    policy_id: str = Field(default_factory=lambda: f"pol-{uuid.uuid4().hex[:8]}")
    title: str
    policy_rule: str
    domain: str = "SoC Security"
    threat_model_ref: Optional[str] = None
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    status: PolicyStatus = PolicyStatus.CANDIDATE
    author_role: str = "Policy Generation"
    provenance: str = "Automated policy generator from validated evidence"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ClosureSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: f"close-{uuid.uuid4().hex[:8]}")
    plan_id: str
    run_id: Optional[str] = None
    requirement_coverage_pct: float = 0.0
    objective_coverage_pct: float = 0.0
    total_requirements: int = 0
    covered_requirements: int = 0
    total_objectives: int = 0
    covered_objectives: int = 0
    open_gaps_count: int = 0
    waivers_count: int = 0
    evidence_items_count: int = 0
    is_closed: bool = False
    status: str = "OPEN"
    sign_off_by: Optional[str] = None
    sign_off_notes: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
