"""
LLMorch Memory System - Promotion & Privacy Gate Engine (Phase 6)
Promotes project-local research outcomes to generalized global research patterns.
Enforces strict privacy boundaries, excluding raw paths, secrets, credentials, and project identity.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from schemas.memory import (
    PatternRecord,
    ProjectMemoryRecord,
    ResearchOutcomeRecord,
    MemoryPromotionRecord,
    PatternDomain,
    MemoryConfidence,
    MemoryPrivacyClass,
)
from schemas.event import Event, EventType
from memory.fingerprint import FingerprintEngine
from history.database import DatabaseService
from history.repositories import GlobalPatternRepository, MemoryPromotionRepository, EventRepository

logger = logging.getLogger(__name__)


class PromotionEngine:
    """
    Privacy Gate & Memory Promotion Manager.
    Sanitizes repository artifacts, checks privacy policy, abstracts structural patterns,
    merges duplicate patterns, and persists global research memory records.
    """

    # Secret / credential patterns to strictly reject
    SENSITIVE_PATTERNS = [
        re.compile(r'api[_-]?key\s*[:=]\s*[\'"][A-Za-z0-9_\-]{16,}[\'"]', re.IGNORECASE),
        re.compile(r'bearer\s+[A-Za-z0-9\-\._~\+\/]+=*', re.IGNORECASE),
        re.compile(r'-----BEGIN\s+(RSA|EC|DSA|OPENSSH|PRIVATE)\s+KEY-----'),
        re.compile(r'password\s*[:=]\s*[\'"][^\'"]+[\'"]', re.IGNORECASE),
        re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), # Email
    ]

    def __init__(self, db_service: DatabaseService):
        self.db = db_service
        self.pattern_repo = GlobalPatternRepository(self.db)
        self.promotion_repo = MemoryPromotionRepository(self.db)
        self.event_repo = EventRepository(self.db)

    @classmethod
    def sanitize_text(cls, text: str) -> Tuple[str, List[str]]:
        """
        Removes file paths, project directory references, line numbers, secrets, and credentials.
        Returns (sanitized_text, list_of_sanitized_field_types).
        """
        sanitized_types = []
        cleaned = text

        # Check for sensitive credentials
        for pat in cls.SENSITIVE_PATTERNS:
            if pat.search(cleaned):
                cleaned = pat.sub('[REDACTED_SECRET]', cleaned)
                if "credentials_secret" not in sanitized_types:
                    sanitized_types.append("credentials_secret")

        # Strip Linux/Windows absolute paths
        if re.search(r'/(?:[a-zA-Z0-9_\-\.]+/)+[a-zA-Z0-9_\-\.]+', cleaned):
            cleaned = re.sub(r'/(?:[a-zA-Z0-9_\-\.]+/)+[a-zA-Z0-9_\-\.]+', '[PATH]', cleaned)
            sanitized_types.append("file_path")

        if re.search(r'[A-Za-z]:\\[^\s]+', cleaned):
            cleaned = re.sub(r'[A-Za-z]:\\[^\s]+', '[PATH]', cleaned)
            sanitized_types.append("file_path")

        # Strip specific line numbers
        if re.search(r'line\s+\d+', cleaned, re.IGNORECASE):
            cleaned = re.sub(r'line\s+\d+', '[LINE]', cleaned, flags=re.IGNORECASE)
            sanitized_types.append("line_number")

        return cleaned, list(set(sanitized_types))

    def evaluate_and_promote(
        self,
        outcome: ResearchOutcomeRecord,
        title: str,
        indicators: List[str],
        affected_constructs: List[str],
        validation_method: Optional[str] = None
    ) -> MemoryPromotionRecord:
        """
        Evaluates a project research outcome for global promotion.
        Strips private identifiers, merges duplicates, and saves to global research memory.
        """
        self.event_repo.record(Event(
            event_type=EventType.MEMORY_PROMOTION_PROPOSED,
            actor="promotion_engine",
            payload={"outcome_id": outcome.outcome_id, "project_id": outcome.project_id}
        ))

        # Privacy Gate 1: Check generalizability flag & outcome confidence
        if not outcome.is_generalizable:
            prom = MemoryPromotionRecord(
                project_id=outcome.project_id,
                outcome_id=outcome.outcome_id,
                accepted=False,
                rejection_reason="Outcome marked not generalizable",
                sanitized_fields=[]
            )
            self.promotion_repo.save(prom)
            self.event_repo.record(Event(
                event_type=EventType.MEMORY_PROMOTION_REJECTED,
                actor="promotion_engine",
                payload={"promotion_id": prom.promotion_id, "reason": prom.rejection_reason}
            ))
            return prom

        # Privacy Gate 2: Check hypothesis content for sensitive leakage
        sanitized_hyp, hyp_san_types = self.sanitize_text(outcome.hypothesis)
        sanitized_title, title_san_types = self.sanitize_text(title)
        all_san_types = list(set(hyp_san_types + title_san_types))

        if "[REDACTED_SECRET]" in sanitized_hyp or "[REDACTED_SECRET]" in sanitized_title:
            prom = MemoryPromotionRecord(
                project_id=outcome.project_id,
                outcome_id=outcome.outcome_id,
                accepted=False,
                rejection_reason="Contains unresolvable sensitive secrets or credentials",
                sanitized_fields=all_san_types
            )
            self.promotion_repo.save(prom)
            self.event_repo.record(Event(
                event_type=EventType.MEMORY_PROMOTION_REJECTED,
                actor="promotion_engine",
                payload={"promotion_id": prom.promotion_id, "reason": prom.rejection_reason}
            ))
            return prom

        # Compute deterministic signatures
        struct_sig = FingerprintEngine.compute_structural_signature(outcome.domain.value, indicators, affected_constructs)
        sem_sig = FingerprintEngine.compute_semantic_signature(sanitized_hyp)

        # Check for Duplicate Pattern in Global Research Memory
        existing_patterns = self.pattern_repo.list_all()
        duplicate_pattern = None
        for pat in existing_patterns:
            if pat.structural_signature == struct_sig or pat.semantic_signature == sem_sig:
                duplicate_pattern = pat
                break

        if duplicate_pattern:
            # Merge into existing pattern record
            duplicate_pattern.observation_count += 1
            duplicate_pattern.updated_at = datetime.now(timezone.utc)
            if outcome.confidence == MemoryConfidence.VALIDATED:
                duplicate_pattern.confidence_state = MemoryConfidence.VALIDATED
            for ind in indicators:
                if ind not in duplicate_pattern.indicators:
                    duplicate_pattern.indicators.append(ind)

            self.pattern_repo.save(duplicate_pattern)

            prom = MemoryPromotionRecord(
                project_id=outcome.project_id,
                outcome_id=outcome.outcome_id,
                pattern_id=duplicate_pattern.pattern_id,
                accepted=True,
                rejection_reason=None,
                sanitized_fields=all_san_types
            )
            self.promotion_repo.save(prom)

            self.event_repo.record(Event(
                event_type=EventType.MEMORY_PATTERN_MERGED,
                actor="promotion_engine",
                payload={"pattern_id": duplicate_pattern.pattern_id, "observation_count": duplicate_pattern.observation_count}
            ))
            self.event_repo.record(Event(
                event_type=EventType.MEMORY_PROMOTION_ACCEPTED,
                actor="promotion_engine",
                payload={"promotion_id": prom.promotion_id, "pattern_id": duplicate_pattern.pattern_id, "action": "MERGED"}
            ))
            return prom

        # Create New Generalized Global PatternRecord
        new_pattern = PatternRecord(
            domain=outcome.domain,
            title=sanitized_title,
            structural_signature=struct_sig,
            semantic_signature=sem_sig,
            indicators=indicators,
            affected_constructs=affected_constructs,
            supporting_evidence_types=["tool_output", "formal_proof"],
            successful_analysis_steps=outcome.successful_steps,
            rejected_analysis_steps=outcome.rejected_steps,
            validation_method=validation_method or "validator_execution",
            provenance={"domain": outcome.domain.value, "origin_project_hash": FingerprintEngine.compute_semantic_signature(outcome.project_id)},
            confidence_state=outcome.confidence,
            privacy_class=MemoryPrivacyClass.GLOBAL_GENERALIZED
        )
        self.pattern_repo.save(new_pattern)

        prom = MemoryPromotionRecord(
            project_id=outcome.project_id,
            outcome_id=outcome.outcome_id,
            pattern_id=new_pattern.pattern_id,
            accepted=True,
            rejection_reason=None,
            sanitized_fields=all_san_types
        )
        self.promotion_repo.save(prom)

        self.event_repo.record(Event(
            event_type=EventType.MEMORY_PROMOTION_ACCEPTED,
            actor="promotion_engine",
            payload={"promotion_id": prom.promotion_id, "pattern_id": new_pattern.pattern_id, "action": "CREATED"}
        ))
        return prom
