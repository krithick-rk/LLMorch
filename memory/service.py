"""
LLMorch Memory System - Core Service & Retrieval Engine (Phase 6)
Provides deterministic-first memory retrieval, project-scoped memory management,
strategy memory persistence, and privacy-enforced access policy evaluation.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from schemas.memory import (
    PatternRecord,
    ProjectMemoryRecord,
    ResearchStrategyRecord,
    ResearchOutcomeRecord,
    MemoryRetrievalRecord,
    PatternDomain,
    MemoryConfidence,
    MemoryPrivacyClass,
    MatchType,
)
from schemas.event import Event, EventType
from memory.fingerprint import FingerprintEngine
from history.database import DatabaseService
from history.repositories import (
    ProjectMemoryRepository,
    GlobalPatternRepository,
    ResearchStrategyRepository,
    ResearchOutcomeRepository,
    EventRepository,
)

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Central Research Memory Manager.
    Coordinates project memory, global pattern retrieval, deterministic feature matching,
    and strategy historical memory.
    """

    def __init__(self, db_service: DatabaseService):
        self.db = db_service
        self.proj_repo = ProjectMemoryRepository(self.db)
        self.global_repo = GlobalPatternRepository(self.db)
        self.strat_repo = ResearchStrategyRepository(self.db)
        self.outcome_repo = ResearchOutcomeRepository(self.db)
        self.event_repo = EventRepository(self.db)

    def record_project_memory(self, rec: ProjectMemoryRecord) -> ProjectMemoryRecord:
        """Saves a project-scoped memory record."""
        return self.proj_repo.save(rec)

    def list_project_memory(self, project_id: str) -> List[ProjectMemoryRecord]:
        """Lists repository-scoped memory records."""
        return self.proj_repo.list_for_project(project_id)

    def record_strategy(self, strat: ResearchStrategyRecord) -> ResearchStrategyRecord:
        """Records a successful or failed analysis strategy for future research guidance."""
        return self.strat_repo.save(strat)

    def list_strategies(self) -> List[ResearchStrategyRecord]:
        """Lists recorded research strategies."""
        return self.strat_repo.list_all()

    def record_outcome(self, outcome: ResearchOutcomeRecord) -> ResearchOutcomeRecord:
        """Records a research outcome from an execution run."""
        return self.outcome_repo.save(outcome)

    def retrieve(
        self,
        project_id: str,
        domain: PatternDomain,
        target_context: str,
        scoped_indicators: Optional[List[str]] = None,
        top_k: int = 5
    ) -> List[MemoryRetrievalRecord]:
        """
        Executes Deterministic-First Memory Retrieval:
        1. Exact structural signature match
        2. Structural indicator overlap
        3. Feature similarity match
        4. Semantic signature match
        Enforces access policies so global generalized patterns are returned without raw project source.
        """
        self.event_repo.record(Event(
            event_type=EventType.MEMORY_RETRIEVAL_STARTED,
            actor="memory_service",
            payload={"project_id": project_id, "domain": domain.value}
        ))

        indicators = scoped_indicators or []
        features = FingerprintEngine.extract_features(target_context)
        query_struct_sig = FingerprintEngine.compute_structural_signature(domain.value, indicators, features)
        query_sem_sig = FingerprintEngine.compute_semantic_signature(target_context)

        all_patterns = self.global_repo.list_all()
        retrievals: List[MemoryRetrievalRecord] = []

        for pat in all_patterns:
            # Enforce Domain Compatibility if specified
            if domain != PatternDomain.GENERIC and pat.domain != PatternDomain.GENERIC and pat.domain != domain:
                continue

            # Layer 1: EXACT Structural Match
            pat_constructs_in_context = [c for c in pat.affected_constructs if c.lower() in target_context.lower()]
            candidate_sig = FingerprintEngine.compute_structural_signature(
                pat.domain.value if hasattr(pat.domain, "value") else str(pat.domain),
                indicators,
                pat_constructs_in_context
            ) if pat_constructs_in_context else query_struct_sig

            if pat.structural_signature in (query_struct_sig, candidate_sig) and (not pat.indicators or set(indicators) == set(pat.indicators)):
                rec = MemoryRetrievalRecord(
                    pattern_id=pat.pattern_id,
                    match_type=MatchType.EXACT,
                    match_score=1.0,
                    matched_features=features or pat_constructs_in_context,
                    pattern=pat,
                    confidence_state=pat.confidence_state,
                    reason=f"Exact structural signature match ({pat.structural_signature})"
                )
                retrievals.append(rec)
                continue

            # Layer 2: STRUCTURAL Indicator Overlap
            common_indicators = set(indicators) & set(pat.indicators)
            if common_indicators:
                overlap_ratio = len(common_indicators) / max(len(indicators), 1)
                rec = MemoryRetrievalRecord(
                    pattern_id=pat.pattern_id,
                    match_type=MatchType.STRUCTURAL,
                    match_score=round(0.7 + 0.25 * overlap_ratio, 2),
                    matched_features=list(common_indicators),
                    pattern=pat,
                    confidence_state=pat.confidence_state,
                    reason=f"Structural indicator overlap: {list(common_indicators)}"
                )
                retrievals.append(rec)
                continue

            # Layer 3: FEATURE Keyword Extraction Match
            pat_features = FingerprintEngine.extract_features(pat.title + " " + " ".join(pat.indicators))
            common_features = set(features) & set(pat_features)
            if common_features:
                feat_score = round(0.5 + 0.3 * (len(common_features) / max(len(features), 1)), 2)
                rec = MemoryRetrievalRecord(
                    pattern_id=pat.pattern_id,
                    match_type=MatchType.FEATURE,
                    match_score=min(feat_score, 0.85),
                    matched_features=list(common_features),
                    pattern=pat,
                    confidence_state=pat.confidence_state,
                    reason=f"Security feature keyword match: {list(common_features)}"
                )
                retrievals.append(rec)
                continue

            # Layer 4: SEMANTIC Signature Match
            if pat.semantic_signature == query_sem_sig:
                rec = MemoryRetrievalRecord(
                    pattern_id=pat.pattern_id,
                    match_type=MatchType.SEMANTIC,
                    match_score=0.80,
                    matched_features=features,
                    pattern=pat,
                    confidence_state=pat.confidence_state,
                    reason="Semantic pattern signature similarity match"
                )
                retrievals.append(rec)

        # Sort by match_score DESC
        retrievals.sort(key=lambda r: r.match_score, reverse=True)
        results = retrievals[:top_k]

        for r in results:
            self.event_repo.record(Event(
                event_type=EventType.MEMORY_MATCH_FOUND,
                actor="memory_service",
                payload={"pattern_id": r.pattern_id, "match_type": r.match_type.value, "score": r.match_score}
            ))

        return results
