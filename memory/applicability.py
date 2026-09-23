"""
LLMorch Memory System - LLM Applicability Verification Gate (Phase 6)
Evaluates whether a retrieved global pattern is applicable to a scoped AnalysisUnit.
CRITICAL GUARANTEE: Does NOT declare code vulnerable; only determines if pattern warrants investigation.
"""

import logging
from typing import Optional, List, Dict, Any

from schemas.memory import PatternRecord, LLMApplicabilityResult, ApplicabilityStatus
from schemas.event import Event, EventType
from history.database import DatabaseService
from history.repositories import EventRepository

logger = logging.getLogger(__name__)


class LLMApplicabilityVerifier:
    """
    LLM Applicability Verification Gate.
    Determines structural applicability of retrieved research patterns against scoped target code.
    Passes candidate pattern to downstream agents for targeted tool execution & validation.
    """

    def __init__(self, db_service: DatabaseService):
        self.db = db_service
        self.event_repo = EventRepository(self.db)

    def verify_applicability(
        self,
        pattern: PatternRecord,
        target_scope_paths: List[str],
        precheck_findings: List[str]
    ) -> LLMApplicabilityResult:
        """
        Evaluates pattern applicability using deterministic indicator matching & LLM reasoning rules.
        Does NOT declare code vulnerable or bypass validator.
        """
        path_str = " ".join(target_scope_paths).lower()
        findings_str = " ".join(precheck_findings).lower()

        # Match pattern indicators against target scope & precheck findings
        matched_indicators = []
        for ind in pattern.indicators:
            if ind.lower() in path_str or ind.lower() in findings_str:
                matched_indicators.append(ind)

        if len(matched_indicators) >= 1:
            status = ApplicabilityStatus.APPLICABLE
            reasoning = (
                f"Retrieved pattern '{pattern.title}' (ID: {pattern.pattern_id}) matches target scope. "
                f"Matched indicators: {matched_indicators}. Pattern warrants targeted agent investigation."
            )
            req_ev = pattern.supporting_evidence_types or ["tool_output"]
            next_act = pattern.successful_analysis_steps or ["run_static_analysis", "construct_reproducer"]
        elif any(c.lower() in path_str for c in pattern.affected_constructs):
            status = ApplicabilityStatus.UNCERTAIN
            reasoning = (
                f"Retrieved pattern '{pattern.title}' shares affected constructs with target scope, "
                "but explicit indicators were missing in static prechecks. Investigation recommended."
            )
            req_ev = ["detailed_ast_scan"]
            next_act = ["inspect_control_flow"]
        else:
            status = ApplicabilityStatus.NOT_APPLICABLE
            reasoning = (
                f"Retrieved pattern '{pattern.title}' indicators ({pattern.indicators}) "
                "do not match target scope or precheck findings. Pattern rejected for current scope."
            )
            req_ev = []
            next_act = []

        res = LLMApplicabilityResult(
            pattern_id=pattern.pattern_id,
            status=status,
            reasoning_summary=reasoning,
            required_evidence=req_ev,
            suggested_next_actions=next_act
        )

        self.event_repo.record(Event(
            event_type=EventType.MEMORY_PATTERN_APPLICABILITY_CHECKED,
            actor="llm_applicability_verifier",
            payload={"pattern_id": pattern.pattern_id, "status": status.value, "reason": reasoning}
        ))

        return res
