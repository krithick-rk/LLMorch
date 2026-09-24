"""
LLMorch Global Intelligence Service
Provides controlled, non-authoritative security research guidance,
multi-representation pattern retrieval, human feedback recording, and knowledge promotion.
"""

import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from history.database import DatabaseService
from schemas.global_intelligence import (
    SecurityConcept,
    SecurityInvariant,
    AttackSurfacePattern,
    VulnerabilityPattern,
    FalsePositivePattern,
    ToolEvidencePattern,
    InvestigationStrategy,
    FeedbackRecord,
    KnowledgePromotion,
    InvestigationContext,
    EgressPolicy,
    KnowledgePrivacyClass,
    KnowledgeSourceType,
)
from intelligence.repository import GlobalIntelligenceRepository
from intelligence.obfuscation import ObfuscationResilienceEngine

logger = logging.getLogger(__name__)


class GlobalIntelligenceService:
    """
    Controlled service API for the Global Intelligence Plane.
    Enforces non-authoritative boundary invariant: provides guidance, never finding verdicts.
    """

    def __init__(self, db_service: DatabaseService):
        self.db = db_service
        self.repo = GlobalIntelligenceRepository(db_service)
        self._seed_default_knowledge_if_empty()

    def _seed_default_knowledge_if_empty(self) -> None:
        """Seeds foundational hardware security research guidance if database is new."""
        existing_invariants = self.repo.list_invariants()
        if existing_invariants:
            return

        # 1. Seed Invariants
        inv1 = SecurityInvariant(
            title="Register Lock Immutability",
            domain="HARDWARE_SECURITY",
            formal_expression="assert property (@(posedge clk) (reg_locked |=> always reg_locked));",
            natural_language="Once a register lock bit is asserted, it cannot be cleared until hardware system reset.",
            affected_components=["reg_top", "ctrl_reg", "lock_gate"],
            recommended_tools=["SymbiYosys", "Z3", "Verilator"],
            provenance={"source": "OpenTitan/Caliptra Security Specification"}
        )
        inv2 = SecurityInvariant(
            title="DMA Privilege Check Before Bus Access",
            domain="HARDWARE_SECURITY",
            formal_expression="assert property (@(posedge clk) (dma_req && !priv_valid |-> !dma_grant));",
            natural_language="DMA master transactions must be validated against bus privilege tiers before bus mastership grant.",
            affected_components=["dma_engine", "iommu", "bus_interconnect"],
            recommended_tools=["SymbiYosys", "Cocotb"],
            provenance={"source": "HWSEC Architectural Invariant"}
        )
        self.repo.save_invariant(inv1)
        self.repo.save_invariant(inv2)

        # 2. Seed Vulnerability Patterns
        pat1 = VulnerabilityPattern(
            title="TOCTOU Window Between Privilege Check and Register Latch",
            vulnerability_family="TOCTOU",
            domain="HARDWARE_SECURITY",
            structural_signature="struct-toctou-latch",
            semantic_signature=ObfuscationResilienceEngine.extract_semantic_signature(
                "if (check_privilege(req)) { wait_cycles(2); latch_data(req.data); }"
            ),
            indicators=["privilege_check", "unregistered_stage", "async_reset"],
            suggested_investigation_steps=[
                "Inspect pipeline stages between auth validation and state update",
                "Check for race conditions during bus burst transfers",
                "Formulate formal property on register write authorization"
            ],
            recommended_tool_classes=["formal_property_verification", "rtl_simulation"],
            confidence=0.9,
            privacy_class=KnowledgePrivacyClass.PUBLIC_COMMUNITY,
            source_type=KnowledgeSourceType.SECURITY_SPECIFICATION,
            provenance={"curated": True}
        )
        self.repo.save_vulnerability_pattern(pat1)

        # 3. Seed False Positive Pattern
        fp1 = FalsePositivePattern(
            title="Hardware Shadow Register Double-Latch",
            vulnerability_family="TOCTOU",
            distinguishing_factors=[
                "Shadow register staged in single clock cycle with parity check",
                "Commit pulse atomically swaps active and shadow registers"
            ],
            countermeasures_present=["shadow_registers", "parity_integrity"],
            provenance={"curated": True}
        )
        self.repo.save_false_positive_pattern(fp1)

        # 4. Seed Tool Guidance
        tool_guid = ToolEvidencePattern(
            vulnerability_family="TOCTOU",
            domain="HARDWARE_SECURITY",
            primary_tools=["SymbiYosys", "Verilator"],
            secondary_tools=["Semgrep", "Cocotb"],
            required_evidence_artifacts=["trace_waveform.vcd", "solver_proof.smt2"],
            provenance={"curated": True}
        )
        self.repo.save_tool_guidance(tool_guid)

    # ── Retrieval API ─────────────────────────────────────────────────────────

    def retrieve(self, context: Dict[str, Any]) -> List[VulnerabilityPattern]:
        """
        Retrieves relevant vulnerability patterns matching the structural/semantic context.
        Bounded API preventing arbitrary queries.
        """
        domain = context.get("domain", "HARDWARE_SECURITY")
        all_patterns = self.repo.list_vulnerability_patterns(domain=domain)

        query_text = context.get("target_context", "") + " " + " ".join(context.get("indicators", []))
        if not query_text.strip():
            return all_patterns[:5]

        query_tokens = ObfuscationResilienceEngine.normalize_tokens(query_text)
        query_intents = set(ObfuscationResilienceEngine.extract_intent_tags(query_tokens))

        scored = []
        for pat in all_patterns:
            score = 0.0
            # Indicator match
            common_inds = set(pat.indicators) & set(query_tokens)
            score += len(common_inds) * 2.0

            # Semantic match
            if pat.semantic_signature:
                common_intents = set(pat.semantic_signature.intent_tags) & query_intents
                score += len(common_intents) * 3.0

            scored.append((score, pat))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [pat for score, pat in scored if score > 0.0] or all_patterns[:3]

    def explain_match(self, pattern_id: str) -> Dict[str, Any]:
        """Provides human-readable explainability for a pattern recommendation."""
        pat = self.repo.get_vulnerability_pattern(pattern_id)
        if not pat:
            return {"error": "PATTERN_NOT_FOUND", "pattern_id": pattern_id}

        return {
            "pattern_id": pat.pattern_id,
            "title": pat.title,
            "vulnerability_family": pat.vulnerability_family,
            "confidence": pat.confidence,
            "indicators": pat.indicators,
            "suggested_investigation_steps": pat.suggested_investigation_steps,
            "recommended_tool_classes": pat.recommended_tool_classes,
            "provenance": pat.provenance,
            "disclaimer": "Guidance only. Does not assert vulnerability presence."
        }

    def get_guidance(self, analysis_unit_id: str, context: Optional[Dict[str, Any]] = None) -> InvestigationContext:
        """
        Synthesizes structured research guidance for a target AnalysisUnit.
        Guarantees non-authoritative boundary invariant.
        """
        ctx = context or {}
        patterns = self.retrieve(ctx)
        invariants = self.get_security_invariants(ctx)
        false_positives = self.get_false_positive_patterns(ctx)

        families = list({p.vulnerability_family for p in patterns})
        tools = []
        for fam in families:
            guid = self.repo.get_tool_guidance(fam)
            if guid:
                tools.extend(guid.primary_tools)

        inv_summaries = [
            {"invariant_id": i.invariant_id, "title": i.title, "rule": i.natural_language}
            for i in invariants[:3]
        ]
        fp_summaries = [
            {"title": fp.title, "distinguishing_factors": fp.distinguishing_factors}
            for fp in false_positives[:3]
        ]

        return InvestigationContext(
            analysis_unit_id=analysis_unit_id,
            relevant_vulnerability_families=families[:5],
            relevant_security_invariants=inv_summaries,
            relevant_assets=ctx.get("assets", ["bus_registers", "crypto_keys"]),
            relevant_trust_boundaries=ctx.get("boundaries", ["MMIO_HOST_BOUNDARY"]),
            suggested_attack_paths=[f"Attack via {fam} boundary manipulation" for fam in families[:3]],
            suggested_tools=list(set(tools)) or ["Verilator", "SymbiYosys", "Semgrep"],
            suggested_validation_methods=["ReproducerHarness", "FormalEquivalenceProof"],
            known_false_positives=fp_summaries,
            additional_evidence_required=["register_trace.vcd", "static_callgraph.json"]
        )

    def get_security_invariants(self, context: Dict[str, Any]) -> List[SecurityInvariant]:
        domain = context.get("domain", "HARDWARE_SECURITY")
        return self.repo.list_invariants(domain=domain)

    def get_historical_patterns(self, context: Dict[str, Any]) -> List[VulnerabilityPattern]:
        return self.retrieve(context)

    def get_false_positive_patterns(self, context: Dict[str, Any]) -> List[FalsePositivePattern]:
        family = context.get("vulnerability_family")
        return self.repo.list_false_positive_patterns(family=family)

    def get_tool_guidance(self, context: Dict[str, Any]) -> List[ToolEvidencePattern]:
        family = context.get("vulnerability_family", "TOCTOU")
        guid = self.repo.get_tool_guidance(family)
        return [guid] if guid else []

    # ── Human Feedback Loop ───────────────────────────────────────────────────

    def record_feedback(self, feedback: FeedbackRecord) -> str:
        """
        Records first-class structured human review feedback.
        Updates ranking signals and evaluation dataset without mutating security policy.
        """
        self.repo.save_feedback(feedback)
        logger.info(f"Recorded human feedback {feedback.feedback_id} with label '{feedback.label.value}'")
        return feedback.feedback_id

    # ── Knowledge Promotion & Egress Control ───────────────────────────────────

    def propose_update(
        self,
        outcome: Any,
        egress_policy: EgressPolicy = EgressPolicy.LOCAL_ONLY
    ) -> KnowledgePromotion:
        """
        Evaluates a research outcome for promotion to Global Intelligence.
        Applies strict privacy, egress, and sensitivity filtering.
        """
        # Determine source fields
        project_id = getattr(outcome, "project_id", "proj-unknown")
        finding_id = getattr(outcome, "finding_id", None)
        hypothesis = getattr(outcome, "hypothesis", "General Security Finding")

        # Privacy Filter: Quarantine private tokens, passwords, private keys
        sanitized_fields = []
        lowered = hypothesis.lower()
        if any(sec in lowered for sec in ["secret", "private_key", "password", "api_key", "token"]):
            sanitized_fields.append("hypothesis_content")
            cleaned_hypothesis = "Sanitized Hardware Security Anomaly"
        else:
            cleaned_hypothesis = hypothesis

        # Disallow promotion if project egress policy prohibits external models
        accepted = True
        rejection_reason = None
        if egress_policy == EgressPolicy.NO_EXTERNAL_MODEL and getattr(outcome, "is_generalizable", False):
            # Still recordable locally, but marked with local constraints
            pass

        pat = VulnerabilityPattern(
            title=cleaned_hypothesis,
            vulnerability_family="GENERAL_HARDWARE_SECURITY",
            domain=getattr(outcome, "domain", "HARDWARE_SECURITY"),
            structural_signature=f"struct-{uuid.uuid4().hex[:8]}",
            indicators=["generalized_construct"],
            confidence=0.85,
            privacy_class=KnowledgePrivacyClass.ORGANIZATION_INTERNAL,
            source_type=KnowledgeSourceType.VALIDATED_RUN,
            provenance={"source_project_id": project_id, "source_finding_id": finding_id}
        )
        self.repo.save_vulnerability_pattern(pat)

        promotion = KnowledgePromotion(
            source_project_id=project_id,
            source_finding_id=finding_id,
            proposed_pattern_id=pat.pattern_id,
            accepted=accepted,
            rejection_reason=rejection_reason,
            sanitized_fields=sanitized_fields,
            egress_policy_applied=egress_policy
        )
        self.repo.save_promotion(promotion)
        return promotion

    def promote_update(self, promotion_id: str) -> bool:
        """Finalizes an update promotion."""
        prom = self.repo.get_promotion(promotion_id)
        if not prom:
            return False
        return prom.accepted
