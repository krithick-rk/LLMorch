"""
LLMorch Data Contracts - Global Intelligence Plane (Phase 8 Foundation)
Defines machine-readable contracts for reusable, non-authoritative security research guidance,
multi-representation knowledge, obfuscation-resilient signatures, human feedback, and knowledge promotion.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict
import uuid


class EgressPolicy(str, Enum):
    """Egress confidentiality classification for projects and snapshots."""
    LOCAL_ONLY = "LOCAL_ONLY"
    TRUSTED_PROVIDER = "TRUSTED_PROVIDER"
    RESTRICTED_EXTERNAL = "RESTRICTED_EXTERNAL"
    NO_EXTERNAL_MODEL = "NO_EXTERNAL_MODEL"


class KnowledgePrivacyClass(str, Enum):
    """Privacy classification for global knowledge entities."""
    PUBLIC_COMMUNITY = "PUBLIC_COMMUNITY"
    ORGANIZATION_INTERNAL = "ORGANIZATION_INTERNAL"
    PROJECT_PRIVATE = "PROJECT_PRIVATE"


class FeedbackLabel(str, Enum):
    """Structured human review classification labels."""
    CONFIRMED = "CONFIRMED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    MISSED_VULNERABILITY = "MISSED_VULNERABILITY"
    PARTIALLY_CORRECT = "PARTIALLY_CORRECT"
    WRONG_LOCALIZATION = "WRONG_LOCALIZATION"
    WRONG_ATTACK_PATH = "WRONG_ATTACK_PATH"
    WRONG_SECURITY_PROPERTY = "WRONG_SECURITY_PROPERTY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CORRECT_REASONING_WRONG_CONCLUSION = "CORRECT_REASONING_WRONG_CONCLUSION"


class KnowledgeSourceType(str, Enum):
    """Origin source of generalized research knowledge."""
    VALIDATED_RUN = "VALIDATED_RUN"
    HUMAN_CURATED = "HUMAN_CURATED"
    BENCHMARK_DERIVED = "BENCHMARK_DERIVED"
    SECURITY_SPECIFICATION = "SECURITY_SPECIFICATION"


class SemanticSignature(BaseModel):
    """Obfuscation-resilient semantic representation."""
    model_config = ConfigDict(extra="allow")
    signature_id: str = Field(default_factory=lambda: f"sig-sem-{uuid.uuid4().hex[:10]}")
    intent_tags: List[str] = Field(default_factory=list, description="Abstract security intent (e.g. privilege_check, register_lock)")
    token_multiset: List[str] = Field(default_factory=list, description="Normalized canonical semantic tokens")
    control_flow_complexity: str = Field(default="MEDIUM", description="LOW, MEDIUM, HIGH")
    entropy_profile: Optional[float] = Field(default=None)


class BehavioralSignature(BaseModel):
    """Behavioral and state transition trace representation."""
    model_config = ConfigDict(extra="allow")
    signature_id: str = Field(default_factory=lambda: f"sig-beh-{uuid.uuid4().hex[:10]}")
    state_transitions: List[str] = Field(default_factory=list, description="Expected security state transitions")
    observed_side_effects: List[str] = Field(default_factory=list, description="Side effects (bus fault, alert firing)")
    timing_sensitive: bool = Field(default=False)


class SecurityConcept(BaseModel):
    """Core security concept or architectural principle."""
    model_config = ConfigDict(extra="allow")
    concept_id: str = Field(default_factory=lambda: f"concept-{uuid.uuid4().hex[:10]}")
    name: str = Field(..., description="Concept name (e.g., Hardware Root of Trust, Secure Boot Chain)")
    domain: str = Field(default="HARDWARE_SECURITY", description="Target security domain")
    description: str = Field(..., description="Detailed concept explanation")
    related_cwe: List[str] = Field(default_factory=list, description="Associated CWE/CAPEC identifiers")
    provenance: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SecurityInvariant(BaseModel):
    """Temporal or structural security invariant that must hold in secure designs."""
    model_config = ConfigDict(extra="allow")
    invariant_id: str = Field(default_factory=lambda: f"inv-{uuid.uuid4().hex[:10]}")
    title: str = Field(..., description="Invariant title")
    domain: str = Field(default="HARDWARE_SECURITY")
    formal_expression: Optional[str] = Field(default=None, description="SVA, LTL, or pseudocode expression")
    natural_language: str = Field(..., description="Plain language explanation of the invariant")
    affected_components: List[str] = Field(default_factory=list)
    recommended_tools: List[str] = Field(default_factory=list, description="Tools capable of verifying (e.g., SymbiYosys, Z3, Cocotb)")
    provenance: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AttackSurfacePattern(BaseModel):
    """Generalized attack surface archetype."""
    model_config = ConfigDict(extra="allow")
    pattern_id: str = Field(default_factory=lambda: f"asp-{uuid.uuid4().hex[:10]}")
    name: str = Field(..., description="Attack surface archetype name")
    boundary_type: str = Field(..., description="Boundary type (HW_SW_MMIO, MAILBOX, JTAG, DMA)")
    entry_points: List[str] = Field(default_factory=list)
    common_attack_paths: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VulnerabilityPattern(BaseModel):
    """Reusable vulnerability archetype with multi-representation signatures."""
    model_config = ConfigDict(extra="allow")
    pattern_id: str = Field(default_factory=lambda: f"vuln-pat-{uuid.uuid4().hex[:10]}")
    title: str = Field(..., description="Pattern title")
    vulnerability_family: str = Field(..., description="Family (e.g. TOCTOU, Privilege Escalation, Clock Glitch Bypass)")
    domain: str = Field(default="HARDWARE_SECURITY")
    structural_signature: str = Field(..., description="Abstract AST/structural fingerprint")
    semantic_signature: Optional[SemanticSignature] = Field(default=None)
    behavioral_signature: Optional[BehavioralSignature] = Field(default=None)
    indicators: List[str] = Field(default_factory=list, description="High-signal abstract indicators")
    suggested_investigation_steps: List[str] = Field(default_factory=list)
    recommended_tool_classes: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    privacy_class: KnowledgePrivacyClass = Field(default=KnowledgePrivacyClass.ORGANIZATION_INTERNAL)
    source_type: KnowledgeSourceType = Field(default=KnowledgeSourceType.VALIDATED_RUN)
    observation_count: int = Field(default=1)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = Field(default="1.0.0")


class FalsePositivePattern(BaseModel):
    """Pattern capturing benign structures frequently mistaken for vulnerabilities."""
    model_config = ConfigDict(extra="allow")
    fp_id: str = Field(default_factory=lambda: f"fp-pat-{uuid.uuid4().hex[:10]}")
    title: str = Field(..., description="Benign pattern title")
    vulnerability_family: str = Field(...)
    distinguishing_factors: List[str] = Field(default_factory=list, description="Why this construct is actually safe")
    countermeasures_present: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ToolEvidencePattern(BaseModel):
    """Guidance mapping vulnerability families to deterministic evidence tools."""
    model_config = ConfigDict(extra="allow")
    guidance_id: str = Field(default_factory=lambda: f"tool-guid-{uuid.uuid4().hex[:10]}")
    vulnerability_family: str = Field(...)
    domain: str = Field(default="HARDWARE_SECURITY")
    primary_tools: List[str] = Field(default_factory=list)
    secondary_tools: List[str] = Field(default_factory=list)
    required_evidence_artifacts: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class InvestigationStrategy(BaseModel):
    """Historical strategy outcome tracking what worked and what failed."""
    model_config = ConfigDict(extra="allow")
    strategy_id: str = Field(default_factory=lambda: f"strat-{uuid.uuid4().hex[:10]}")
    vulnerability_family: str = Field(...)
    recommended_decomposition: List[str] = Field(default_factory=list)
    success_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    historical_failures: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class FeedbackRecord(BaseModel):
    """First-class structured human review and evaluation record."""
    model_config = ConfigDict(extra="allow")
    feedback_id: str = Field(default_factory=lambda: f"fb-{uuid.uuid4().hex[:10]}")
    finding_id: Optional[str] = Field(default=None)
    hypothesis_reference: Optional[str] = Field(default=None)
    project_id: str = Field(...)
    snapshot_id: Optional[str] = Field(default=None)
    analysis_unit_id: Optional[str] = Field(default=None)
    reviewer: str = Field(default="human_expert")
    label: FeedbackLabel = Field(...)
    reason: str = Field(..., description="Detailed rationale for feedback")
    corrected_localization: Optional[Dict[str, Any]] = Field(default=None)
    corrected_security_property: Optional[str] = Field(default=None)
    corrected_attack_path: Optional[str] = Field(default=None)
    supporting_evidence_refs: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgePromotion(BaseModel):
    """Audit record for promoting project-local outcomes to Global Intelligence."""
    model_config = ConfigDict(extra="allow")
    promotion_id: str = Field(default_factory=lambda: f"prom-{uuid.uuid4().hex[:10]}")
    source_project_id: str = Field(...)
    source_finding_id: Optional[str] = Field(default=None)
    proposed_pattern_id: str = Field(...)
    accepted: bool = Field(default=False)
    rejection_reason: Optional[str] = Field(default=None)
    sanitized_fields: List[str] = Field(default_factory=list)
    egress_policy_applied: EgressPolicy = Field(default=EgressPolicy.LOCAL_ONLY)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InvestigationContext(BaseModel):
    """Non-authoritative research guidance synthesized for agents."""
    model_config = ConfigDict(extra="allow")
    analysis_unit_id: str = Field(...)
    relevant_vulnerability_families: List[str] = Field(default_factory=list)
    relevant_security_invariants: List[Dict[str, Any]] = Field(default_factory=list)
    relevant_assets: List[str] = Field(default_factory=list)
    relevant_trust_boundaries: List[str] = Field(default_factory=list)
    suggested_attack_paths: List[str] = Field(default_factory=list)
    suggested_tools: List[str] = Field(default_factory=list)
    suggested_validation_methods: List[str] = Field(default_factory=list)
    known_false_positives: List[Dict[str, Any]] = Field(default_factory=list)
    historical_strategy_outcomes: List[Dict[str, Any]] = Field(default_factory=list)
    additional_evidence_required: List[str] = Field(default_factory=list)
    disclaimer: str = Field(
        default="GLOBAL INTELLIGENCE GUIDANCE IS NON-AUTHORITATIVE. Final finding validity is determined exclusively by the Validator.",
        description="Architectural boundary invariant notice"
    )
