"""
Unit & Integration Tests - Global Intelligence Plane & Human Feedback Loop
Validates non-authoritative guidance, multi-representation knowledge, human feedback recording,
sensitivity/privacy filtering, and update promotion.
"""

import pytest
from pathlib import Path
from datetime import datetime, timezone

from history.database import DatabaseService
from schemas.global_intelligence import (
    SecurityConcept,
    SecurityInvariant,
    AttackSurfacePattern,
    VulnerabilityPattern,
    FalsePositivePattern,
    ToolEvidencePattern,
    FeedbackRecord,
    FeedbackLabel,
    EgressPolicy,
    KnowledgePrivacyClass,
    KnowledgeSourceType,
    InvestigationContext,
)
from intelligence.service import GlobalIntelligenceService
from intelligence.repository import GlobalIntelligenceRepository
from intelligence.obfuscation import ObfuscationResilienceEngine


@pytest.fixture
def db():
    return DatabaseService(":memory:")


@pytest.fixture
def service(db):
    return GlobalIntelligenceService(db)


def test_global_intelligence_seeding(service):
    """Verifies default hardware security invariants and patterns are seeded."""
    invariants = service.get_security_invariants({})
    assert len(invariants) >= 2
    titles = [i.title for i in invariants]
    assert "Register Lock Immutability" in titles
    assert "DMA Privilege Check Before Bus Access" in titles


def test_non_authoritative_guidance_invariant(service):
    """
    CRITICAL INVARIANT: Global Intelligence guidance must NEVER issue a finding verdict.
    It returns structured research guidance with an explicit non-authoritative disclaimer.
    """
    guidance = service.get_guidance(
        analysis_unit_id="unit-dma-01",
        context={"target_context": "dma privilege lock register", "indicators": ["dma", "privilege_check"]}
    )

    assert isinstance(guidance, InvestigationContext)
    assert guidance.analysis_unit_id == "unit-dma-01"
    assert "NON-AUTHORITATIVE" in guidance.disclaimer
    assert len(guidance.relevant_vulnerability_families) >= 1
    assert len(guidance.suggested_tools) >= 1
    assert len(guidance.relevant_security_invariants) >= 1


def test_explain_match_api(service):
    """Verifies explainability API provides human-readable rationale."""
    patterns = service.retrieve({"target_context": "toctou privilege check latch"})
    assert len(patterns) >= 1
    pat_id = patterns[0].pattern_id

    explanation = service.explain_match(pat_id)
    assert explanation["pattern_id"] == pat_id
    assert "vulnerability_family" in explanation
    assert "suggested_investigation_steps" in explanation
    assert "disclaimer" in explanation


def test_human_feedback_recording_first_class(service, db):
    """
    Verifies human reviewer classifications (CONFIRMED, FALSE_POSITIVE, etc.)
    are persisted as first-class structured feedback records.
    """
    feedback = FeedbackRecord(
        finding_id="find-987",
        project_id="proj-hwsec-eval",
        reviewer="senior_hwsec_analyst",
        label=FeedbackLabel.FALSE_POSITIVE,
        reason="Hardware shadow register double-latch prevents TOCTOU race condition",
        corrected_security_property="Register write latches atomically on commit pulse",
        supporting_evidence_refs=["ev-waveform-01"]
    )

    fb_id = service.record_feedback(feedback)
    assert fb_id.startswith("fb-")

    retrieved = service.repo.list_feedback(project_id="proj-hwsec-eval")
    assert len(retrieved) == 1
    rec = retrieved[0]
    assert rec.label == FeedbackLabel.FALSE_POSITIVE
    assert "shadow register" in rec.reason


def test_privacy_filter_and_egress_policy_promotion(service):
    """
    Verifies privacy filter quarantees sensitive tokens (private_key, secret, api_key)
    before knowledge promotion to the global plane.
    """
    class MockResearchOutcome:
        project_id = "proj-secure-vault"
        finding_id = "fnd-123"
        hypothesis = "Buffer overflow leaking private_key in keymgr_read_token"
        domain = "HARDWARE_SECURITY"
        is_generalizable = True

    outcome = MockResearchOutcome()
    promotion = service.propose_update(outcome, egress_policy=EgressPolicy.LOCAL_ONLY)

    assert promotion.accepted is True
    assert "hypothesis_content" in promotion.sanitized_fields
    assert promotion.egress_policy_applied == EgressPolicy.LOCAL_ONLY

    # Confirm promoted pattern title is sanitized
    promoted_pat = service.repo.get_vulnerability_pattern(promotion.proposed_pattern_id)
    assert "private_key" not in promoted_pat.title
    assert "Sanitized" in promoted_pat.title
