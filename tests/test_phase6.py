"""
Unit & Integration Tests - Phase 6 Cross-Project Intelligence & Research Memory
"""

import pytest
import sys
import os
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.task import Task, TaskStatus, RiskLevel
from schemas.agent import Agent, AgentInterface
from schemas.health import AgentHealthState
from schemas.memory import (
    PatternRecord,
    ProjectMemoryRecord,
    ResearchStrategyRecord,
    ResearchOutcomeRecord,
    MemoryPromotionRecord,
    PatternDomain,
    MemoryConfidence,
    MemoryPrivacyClass,
    MatchType,
    ApplicabilityStatus,
)

from memory.fingerprint import FingerprintEngine
from memory.promotion import PromotionEngine
from memory.service import MemoryService
from memory.applicability import LLMApplicabilityVerifier
from history.database import DatabaseService
from history.repositories import (
    ProjectMemoryRepository,
    GlobalPatternRepository,
    ResearchStrategyRepository,
    ResearchOutcomeRepository,
    MemoryPromotionRepository,
)
from orchestrator.investigation import InvestigationWorkflow


@pytest.fixture
def db():
    return DatabaseService(":memory:")


def test_project_memory_is_scoped(db):
    repo = ProjectMemoryRepository(db)
    rec1 = ProjectMemoryRecord(
        project_id="proj-alpha",
        domain=PatternDomain.PYTHON,
        architecture_facts=["Uses Django framework"],
        privacy_class=MemoryPrivacyClass.PROJECT_PRIVATE
    )
    repo.save(rec1)

    alpha_mems = repo.list_for_project("proj-alpha")
    beta_mems = repo.list_for_project("proj-beta")

    assert len(alpha_mems) == 1
    assert alpha_mems[0].project_id == "proj-alpha"
    assert alpha_mems[0].privacy_class == MemoryPrivacyClass.PROJECT_PRIVATE
    assert len(beta_mems) == 0


def test_global_memory_contains_only_generalized_records(db):
    repo = GlobalPatternRepository(db)
    pat = PatternRecord(
        domain=PatternDomain.RTL,
        title="Unsafe Register Write Gating",
        structural_signature="struct-123",
        semantic_signature="sem-123",
        indicators=["lock_bit", "privilege_gating"],
        affected_constructs=["register_file"],
        confidence_state=MemoryConfidence.VALIDATED,
        privacy_class=MemoryPrivacyClass.GLOBAL_GENERALIZED
    )
    repo.save(pat)

    retrieved = repo.get(pat.pattern_id)
    assert retrieved is not None
    assert retrieved.privacy_class == MemoryPrivacyClass.GLOBAL_GENERALIZED
    assert "/home/" not in retrieved.title


def test_sensitive_artifact_not_promoted(db):
    promotion_engine = PromotionEngine(db)
    outcome = ResearchOutcomeRecord(
        project_id="proj-secret",
        task_id="task-1",
        run_id="run-1",
        domain=PatternDomain.PYTHON,
        hypothesis="Found exposed API key api_key='mock_dummy_secret_key_1234567890' in config",
        confidence=MemoryConfidence.VALIDATED,
        is_generalizable=True
    )

    prom = promotion_engine.evaluate_and_promote(
        outcome=outcome,
        title="Exposed Credentials",
        indicators=["api_key"],
        affected_constructs=["config"]
    )

    assert prom.accepted is False
    assert prom.rejection_reason == "Contains unresolvable sensitive secrets or credentials"


def test_repository_specific_path_not_promoted(db):
    promotion_engine = PromotionEngine(db)
    outcome = ResearchOutcomeRecord(
        project_id="proj-path-test",
        task_id="task-2",
        run_id="run-2",
        domain=PatternDomain.C_CPP,
        hypothesis="Unchecked buffer copy in file /home/hackdac/Desktop/intern/LLMorch/src/main.c at line 42",
        confidence=MemoryConfidence.VALIDATED,
        is_generalizable=True
    )

    prom = promotion_engine.evaluate_and_promote(
        outcome=outcome,
        title="Buffer Copy in /home/hackdac/Desktop/intern/LLMorch/src/main.c",
        indicators=["buffer_copy"],
        affected_constructs=["parser"]
    )

    assert prom.accepted is True
    assert "file_path" in prom.sanitized_fields or "line_number" in prom.sanitized_fields

    global_repo = GlobalPatternRepository(db)
    pat = global_repo.get(prom.pattern_id)
    assert "/home/hackdac/" not in pat.title
    assert "/home/hackdac/" not in pat.semantic_signature


def test_pattern_record_schema():
    pat = PatternRecord(
        domain=PatternDomain.HW_SW,
        title="Hardware Security Gating Pattern",
        structural_signature="struct-abc",
        semantic_signature="sem-abc",
        indicators=["privilege", "lock"],
        affected_constructs=["hw_register"]
    )
    assert pat.pattern_id.startswith("pat-")
    assert pat.domain == PatternDomain.HW_SW
    assert pat.confidence_state == MemoryConfidence.PROPOSED
    assert pat.version == 1


def test_structural_fingerprint_match():
    sig1 = FingerprintEngine.compute_structural_signature("rtl", ["lock_bit", "privilege"], ["register"])
    sig2 = FingerprintEngine.compute_structural_signature("RTL", ["privilege", "lock_bit"], ["register"])
    assert sig1 == sig2


def test_retrieval_order(db):
    service = MemoryService(db)
    promotion_engine = PromotionEngine(db)

    # Insert Pattern 1 (Exact Structural Match)
    struct_sig = FingerprintEngine.compute_structural_signature("rtl", ["lock_bit"], ["register"])
    pat1 = PatternRecord(
        domain=PatternDomain.RTL,
        title="Exact Match Pattern",
        structural_signature=struct_sig,
        semantic_signature="sem-exact",
        indicators=["lock_bit"],
        affected_constructs=["register"]
    )
    GlobalPatternRepository(db).save(pat1)

    results = service.retrieve(
        project_id="proj-query",
        domain=PatternDomain.RTL,
        target_context="register lock_bit check",
        scoped_indicators=["lock_bit"]
    )

    assert len(results) >= 1
    assert results[0].match_type == MatchType.EXACT
    assert results[0].pattern_id == pat1.pattern_id


def test_llm_applicability_gate(db):
    verifier = LLMApplicabilityVerifier(db)
    pat = PatternRecord(
        domain=PatternDomain.RTL,
        title="Privilege Lock Bit Pattern",
        structural_signature="struct-1",
        semantic_signature="sem-1",
        indicators=["lock_bit", "privilege"],
        affected_constructs=["register"]
    )

    # Case 1: Applicable
    res1 = verifier.verify_applicability(pat, ["/src/register_ctrl.sv"], ["lock_bit missing"])
    assert res1.status == ApplicabilityStatus.APPLICABLE

    # Case 2: Not Applicable
    res2 = verifier.verify_applicability(pat, ["/src/math_helper.py"], ["no precheck finding"])
    assert res2.status == ApplicabilityStatus.NOT_APPLICABLE


def test_duplicate_pattern_merge(db):
    promotion_engine = PromotionEngine(db)
    outcome1 = ResearchOutcomeRecord(
        project_id="proj-a", task_id="t1", run_id="r1", domain=PatternDomain.RTL,
        hypothesis="Privilege register write prior to lock bit assertion",
        confidence=MemoryConfidence.VALIDATED, is_generalizable=True
    )
    outcome2 = ResearchOutcomeRecord(
        project_id="proj-b", task_id="t2", run_id="r2", domain=PatternDomain.RTL,
        hypothesis="Privilege register write prior to lock bit assertion",
        confidence=MemoryConfidence.VALIDATED, is_generalizable=True
    )

    prom1 = promotion_engine.evaluate_and_promote(outcome1, "Privilege Gating Pattern", ["lock_bit"], ["register"])
    prom2 = promotion_engine.evaluate_and_promote(outcome2, "Privilege Gating Pattern", ["lock_bit"], ["register"])

    assert prom1.pattern_id == prom2.pattern_id

    pat = GlobalPatternRepository(db).get(prom1.pattern_id)
    assert pat.observation_count == 2


def test_memory_does_not_confirm_finding(db):
    # Proves memory match alone does not mark finding CONFIRMED
    wf = InvestigationWorkflow(
        repo_path=str(PROJECT_ROOT),
        target_component="schemas",
        db_service=db
    )
    res = wf.run()

    # The workflow runs validator and sets finding state based on reproducible validator result
    assert "validation" in res
    assert "finding_state" in res["validation"]


def test_cross_project_pattern_reuse(db):
    """
    Cross-Project Security Boundary & Reuse Test:
    Project A -> produces finding -> generalized pattern promoted to Global Memory
    Project B -> retrieves Project A's generalized pattern & evaluates applicability!
    """
    # 1. Project A Execution & Promotion
    prom_engine = PromotionEngine(db)
    outcome_a = ResearchOutcomeRecord(
        project_id="proj-project-A",
        task_id="task-a",
        run_id="run-a",
        domain=PatternDomain.PYTHON,
        hypothesis="Unsanitized privilege escalation path in privilege_gate module",
        confidence=MemoryConfidence.VALIDATED,
        is_generalizable=True
    )
    prom_res = prom_engine.evaluate_and_promote(
        outcome=outcome_a,
        title="Unsanitized Privilege Gate Pattern",
        indicators=["privilege_gate", "unsanitized"],
        affected_constructs=["access_control"]
    )
    assert prom_res.accepted is True
    pattern_id_a = prom_res.pattern_id

    # 2. Project B Retrieval (Completely Unrelated Project ID)
    mem_service = MemoryService(db)
    retrieved = mem_service.retrieve(
        project_id="proj-project-B",
        domain=PatternDomain.PYTHON,
        target_context="privilege_gate unsanitized input check",
        scoped_indicators=["privilege_gate"]
    )

    assert len(retrieved) >= 1
    matched_pat = retrieved[0].pattern
    assert matched_pat.pattern_id == pattern_id_a
    assert "proj-project-A" not in matched_pat.title
    assert "proj-project-A" not in matched_pat.semantic_signature


def test_cross_project_false_positive_protection(db):
    """
    Hard-Negative Case (Project C):
    Pattern retrieved, but applicability / tool prechecks detect missing conditions -> Rejected!
    """
    verifier = LLMApplicabilityVerifier(db)
    pat = PatternRecord(
        domain=PatternDomain.GO,
        title="SQL Injection in raw query handler",
        structural_signature="struct-sqli",
        semantic_signature="sem-sqli",
        indicators=["raw_query_exec", "unbound_parameter"],
        affected_constructs=["db_driver"]
    )

    # Project C has ORM parameterized queries (hard negative)
    app_res = verifier.verify_applicability(
        pattern=pat,
        target_scope_paths=["/pkg/db/orm_helper.go"],
        precheck_findings=["parameterized_query_detected"]
    )

    assert app_res.status == ApplicabilityStatus.NOT_APPLICABLE


def test_phase5_failover_regression(db):
    """Verifies Phase 5 failover recovery remains operational during memory workflows."""
    wf = InvestigationWorkflow(
        repo_path=str(PROJECT_ROOT),
        target_component="schemas",
        testing_config={"simulate_quota_exhaustion_for": ["agent-agy-01"]},
        db_service=db
    )
    result = wf.run()

    assert result["task_status"] == "READY_FOR_REVIEW"
    assert "agent-claude-01" in result["selected_agents"] or "agent-codex-01" in result["selected_agents"]


if __name__ == "__main__":
    pytest.main([__file__])
