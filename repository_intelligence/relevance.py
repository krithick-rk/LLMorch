"""
LLMorch Repository Intelligence - Relevance Engine (Phase 7)
Deterministic relevance scoring and priority assignment for AnalysisUnits.
"""

from typing import List, Dict, Any, Optional, Tuple
from schemas.analysis_unit import AnalysisUnit, PriorityLevel
from schemas.file_classification import FileClassificationRecord
from schemas.repository_intelligence import ReachabilityStatus


# Transparent scoring weights
WEIGHT_TRUST_BOUNDARY = 0.25
WEIGHT_ASSET_PRESENT = 0.20
WEIGHT_REACHABILITY = 0.20
WEIGHT_SECURITY_PROP = 0.15
WEIGHT_COUNTERMEASURE = 0.10
WEIGHT_ENTRY_POINT = 0.10


class RelevanceEngine:
    """
    Deterministic relevance scorer for AnalysisUnits.
    Scores are computed from transparent signal weights; reasons are always surfaced.
    """

    @classmethod
    def score_unit(
        cls,
        unit: AnalysisUnit,
        reachability: ReachabilityStatus = ReachabilityStatus.UNKNOWN,
    ) -> Tuple[AnalysisUnit, List[str]]:
        """
        Computes relevance_score and priority for an AnalysisUnit.
        Returns (updated_unit, list_of_score_reasons).
        """
        score = 0.0
        reasons: List[str] = []

        if unit.trust_boundaries:
            score += WEIGHT_TRUST_BOUNDARY
            reasons.append(f"Trust boundary present (+{WEIGHT_TRUST_BOUNDARY}): {unit.trust_boundaries}")

        if unit.assets:
            score += WEIGHT_ASSET_PRESENT
            reasons.append(f"Sensitive assets present (+{WEIGHT_ASSET_PRESENT}): {unit.assets}")

        if reachability in (ReachabilityStatus.REACHABLE, ReachabilityStatus.LIKELY_REACHABLE):
            score += WEIGHT_REACHABILITY
            reasons.append(f"Reachable from entry point (+{WEIGHT_REACHABILITY}): {reachability.value}")
        elif reachability == ReachabilityStatus.POSSIBLY_REACHABLE:
            score += WEIGHT_REACHABILITY * 0.5
            reasons.append(f"Possibly reachable (+{WEIGHT_REACHABILITY * 0.5}): {reachability.value}")

        if unit.security_properties:
            score += WEIGHT_SECURITY_PROP
            reasons.append(f"Security properties present (+{WEIGHT_SECURITY_PROP})")

        if unit.countermeasures:
            score += WEIGHT_COUNTERMEASURE
            reasons.append(f"Countermeasures detected (+{WEIGHT_COUNTERMEASURE}): warrants verification")

        if unit.entry_points:
            score += WEIGHT_ENTRY_POINT
            reasons.append(f"Entry points exposed (+{WEIGHT_ENTRY_POINT}): {unit.entry_points}")

        unit.relevance_score = round(min(score, 1.0), 4)
        unit.priority = cls._score_to_priority(unit.relevance_score)
        return unit, reasons

    @classmethod
    def _score_to_priority(cls, score: float) -> PriorityLevel:
        if score >= 0.75:
            return PriorityLevel.CRITICAL
        elif score >= 0.55:
            return PriorityLevel.HIGH
        elif score >= 0.35:
            return PriorityLevel.MEDIUM
        elif score >= 0.15:
            return PriorityLevel.LOW
        else:
            return PriorityLevel.IGNORE
