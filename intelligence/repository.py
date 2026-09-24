"""
LLMorch Persistence - Global Intelligence Repository
Implements backend-neutral structured storage for global concepts, invariants,
attack surface archetypes, vulnerability patterns, human feedback records, and promotions.
"""

import json
import logging
from typing import List, Optional, Dict, Any
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
    SemanticSignature,
    BehavioralSignature,
)

logger = logging.getLogger(__name__)


class GlobalIntelligenceRepository:
    """Backend-neutral SQLite repository for the Global Intelligence Plane."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    # ── Security Concepts ─────────────────────────────────────────────────────

    def save_concept(self, concept: SecurityConcept) -> None:
        query = """
        INSERT OR REPLACE INTO global_concepts (
            concept_id, name, domain, description, related_cwe, provenance, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.get_connection() as conn:
            conn.execute(query, (
                concept.concept_id,
                concept.name,
                concept.domain,
                concept.description,
                json.dumps(concept.related_cwe),
                json.dumps(concept.provenance),
                concept.created_at.isoformat()
            ))
            conn.commit()

    def get_concept(self, concept_id: str) -> Optional[SecurityConcept]:
        query = "SELECT * FROM global_concepts WHERE concept_id = ?;"
        with self.db.get_connection() as conn:
            row = conn.execute(query, (concept_id,)).fetchone()
            if not row:
                return None
            return SecurityConcept(
                concept_id=row["concept_id"],
                name=row["name"],
                domain=row["domain"],
                description=row["description"],
                related_cwe=json.loads(row["related_cwe"]),
                provenance=json.loads(row["provenance"]),
                created_at=datetime.fromisoformat(row["created_at"])
            )

    def list_concepts(self, domain: Optional[str] = None) -> List[SecurityConcept]:
        query = "SELECT * FROM global_concepts"
        params = ()
        if domain:
            query += " WHERE domain = ?"
            params = (domain,)
        query += ";"

        with self.db.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                SecurityConcept(
                    concept_id=r["concept_id"],
                    name=r["name"],
                    domain=r["domain"],
                    description=r["description"],
                    related_cwe=json.loads(r["related_cwe"]),
                    provenance=json.loads(r["provenance"]),
                    created_at=datetime.fromisoformat(r["created_at"])
                )
                for r in rows
            ]

    # ── Security Invariants ───────────────────────────────────────────────────

    def save_invariant(self, inv: SecurityInvariant) -> None:
        query = """
        INSERT OR REPLACE INTO security_invariants (
            invariant_id, title, domain, formal_expression, natural_language,
            affected_components, recommended_tools, provenance, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.get_connection() as conn:
            conn.execute(query, (
                inv.invariant_id,
                inv.title,
                inv.domain,
                inv.formal_expression,
                inv.natural_language,
                json.dumps(inv.affected_components),
                json.dumps(inv.recommended_tools),
                json.dumps(inv.provenance),
                inv.created_at.isoformat()
            ))
            conn.commit()

    def list_invariants(self, domain: Optional[str] = None) -> List[SecurityInvariant]:
        query = "SELECT * FROM security_invariants"
        params = ()
        if domain:
            query += " WHERE domain = ?"
            params = (domain,)
        query += ";"

        with self.db.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                SecurityInvariant(
                    invariant_id=r["invariant_id"],
                    title=r["title"],
                    domain=r["domain"],
                    formal_expression=r["formal_expression"],
                    natural_language=r["natural_language"],
                    affected_components=json.loads(r["affected_components"]),
                    recommended_tools=json.loads(r["recommended_tools"]),
                    provenance=json.loads(r["provenance"]),
                    created_at=datetime.fromisoformat(r["created_at"])
                )
                for r in rows
            ]

    # ── Attack Surface Patterns ───────────────────────────────────────────────

    def save_attack_surface_pattern(self, asp: AttackSurfacePattern) -> None:
        query = """
        INSERT OR REPLACE INTO attack_surface_patterns (
            pattern_id, name, boundary_type, entry_points, common_attack_paths,
            required_capabilities, provenance, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.get_connection() as conn:
            conn.execute(query, (
                asp.pattern_id,
                asp.name,
                asp.boundary_type,
                json.dumps(asp.entry_points),
                json.dumps(asp.common_attack_paths),
                json.dumps(asp.required_capabilities),
                json.dumps(asp.provenance),
                asp.created_at.isoformat()
            ))
            conn.commit()

    def list_attack_surface_patterns(self, boundary_type: Optional[str] = None) -> List[AttackSurfacePattern]:
        query = "SELECT * FROM attack_surface_patterns"
        params = ()
        if boundary_type:
            query += " WHERE boundary_type = ?"
            params = (boundary_type,)
        query += ";"

        with self.db.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                AttackSurfacePattern(
                    pattern_id=r["pattern_id"],
                    name=r["name"],
                    boundary_type=r["boundary_type"],
                    entry_points=json.loads(r["entry_points"]),
                    common_attack_paths=json.loads(r["common_attack_paths"]),
                    required_capabilities=json.loads(r["required_capabilities"]),
                    provenance=json.loads(r["provenance"]),
                    created_at=datetime.fromisoformat(r["created_at"])
                )
                for r in rows
            ]

    # ── Vulnerability Patterns ────────────────────────────────────────────────

    def save_vulnerability_pattern(self, pat: VulnerabilityPattern) -> None:
        sem_json = pat.semantic_signature.model_dump_json() if pat.semantic_signature else None
        beh_json = pat.behavioral_signature.model_dump_json() if pat.behavioral_signature else None

        query = """
        INSERT OR REPLACE INTO vulnerability_patterns (
            pattern_id, title, vulnerability_family, domain, structural_signature,
            semantic_signature, behavioral_signature, indicators,
            suggested_investigation_steps, recommended_tool_classes, confidence,
            privacy_class, source_type, observation_count, provenance, created_at, version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.get_connection() as conn:
            conn.execute(query, (
                pat.pattern_id,
                pat.title,
                pat.vulnerability_family,
                pat.domain,
                pat.structural_signature,
                sem_json,
                beh_json,
                json.dumps(pat.indicators),
                json.dumps(pat.suggested_investigation_steps),
                json.dumps(pat.recommended_tool_classes),
                pat.confidence,
                pat.privacy_class.value,
                pat.source_type.value,
                pat.observation_count,
                json.dumps(pat.provenance),
                pat.created_at.isoformat(),
                pat.version
            ))
            conn.commit()

    def get_vulnerability_pattern(self, pattern_id: str) -> Optional[VulnerabilityPattern]:
        query = "SELECT * FROM vulnerability_patterns WHERE pattern_id = ?;"
        with self.db.get_connection() as conn:
            r = conn.execute(query, (pattern_id,)).fetchone()
            if not r:
                return None
            sem = SemanticSignature.model_validate_json(r["semantic_signature"]) if r["semantic_signature"] else None
            beh = BehavioralSignature.model_validate_json(r["behavioral_signature"]) if r["behavioral_signature"] else None
            return VulnerabilityPattern(
                pattern_id=r["pattern_id"],
                title=r["title"],
                vulnerability_family=r["vulnerability_family"],
                domain=r["domain"],
                structural_signature=r["structural_signature"],
                semantic_signature=sem,
                behavioral_signature=beh,
                indicators=json.loads(r["indicators"]),
                suggested_investigation_steps=json.loads(r["suggested_investigation_steps"]),
                recommended_tool_classes=json.loads(r["recommended_tool_classes"]),
                confidence=r["confidence"],
                privacy_class=r["privacy_class"],
                source_type=r["source_type"],
                observation_count=r["observation_count"],
                provenance=json.loads(r["provenance"]),
                created_at=datetime.fromisoformat(r["created_at"]),
                version=r["version"]
            )

    def list_vulnerability_patterns(self, domain: Optional[str] = None) -> List[VulnerabilityPattern]:
        query = "SELECT * FROM vulnerability_patterns"
        params = ()
        if domain:
            query += " WHERE domain = ?"
            params = (domain,)
        query += ";"

        with self.db.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            result = []
            for r in rows:
                sem = SemanticSignature.model_validate_json(r["semantic_signature"]) if r["semantic_signature"] else None
                beh = BehavioralSignature.model_validate_json(r["behavioral_signature"]) if r["behavioral_signature"] else None
                result.append(VulnerabilityPattern(
                    pattern_id=r["pattern_id"],
                    title=r["title"],
                    vulnerability_family=r["vulnerability_family"],
                    domain=r["domain"],
                    structural_signature=r["structural_signature"],
                    semantic_signature=sem,
                    behavioral_signature=beh,
                    indicators=json.loads(r["indicators"]),
                    suggested_investigation_steps=json.loads(r["suggested_investigation_steps"]),
                    recommended_tool_classes=json.loads(r["recommended_tool_classes"]),
                    confidence=r["confidence"],
                    privacy_class=r["privacy_class"],
                    source_type=r["source_type"],
                    observation_count=r["observation_count"],
                    provenance=json.loads(r["provenance"]),
                    created_at=datetime.fromisoformat(r["created_at"]),
                    version=r["version"]
                ))
            return result

    # ── False Positive Patterns ───────────────────────────────────────────────

    def save_false_positive_pattern(self, fp: FalsePositivePattern) -> None:
        query = """
        INSERT OR REPLACE INTO false_positive_patterns (
            fp_id, title, vulnerability_family, distinguishing_factors,
            countermeasures_present, provenance, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.get_connection() as conn:
            conn.execute(query, (
                fp.fp_id,
                fp.title,
                fp.vulnerability_family,
                json.dumps(fp.distinguishing_factors),
                json.dumps(fp.countermeasures_present),
                json.dumps(fp.provenance),
                fp.created_at.isoformat()
            ))
            conn.commit()

    def list_false_positive_patterns(self, family: Optional[str] = None) -> List[FalsePositivePattern]:
        query = "SELECT * FROM false_positive_patterns"
        params = ()
        if family:
            query += " WHERE vulnerability_family = ?"
            params = (family,)
        query += ";"

        with self.db.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                FalsePositivePattern(
                    fp_id=r["fp_id"],
                    title=r["title"],
                    vulnerability_family=r["vulnerability_family"],
                    distinguishing_factors=json.loads(r["distinguishing_factors"]),
                    countermeasures_present=json.loads(r["countermeasures_present"]),
                    provenance=json.loads(r["provenance"]),
                    created_at=datetime.fromisoformat(r["created_at"])
                )
                for r in rows
            ]

    # ── Tool Evidence Patterns ────────────────────────────────────────────────

    def save_tool_guidance(self, tool_pat: ToolEvidencePattern) -> None:
        query = """
        INSERT OR REPLACE INTO tool_evidence_patterns (
            guidance_id, vulnerability_family, domain, primary_tools,
            secondary_tools, required_evidence_artifacts, provenance
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.get_connection() as conn:
            conn.execute(query, (
                tool_pat.guidance_id,
                tool_pat.vulnerability_family,
                tool_pat.domain,
                json.dumps(tool_pat.primary_tools),
                json.dumps(tool_pat.secondary_tools),
                json.dumps(tool_pat.required_evidence_artifacts),
                json.dumps(tool_pat.provenance)
            ))
            conn.commit()

    def get_tool_guidance(self, family: str) -> Optional[ToolEvidencePattern]:
        query = "SELECT * FROM tool_evidence_patterns WHERE vulnerability_family = ?;"
        with self.db.get_connection() as conn:
            r = conn.execute(query, (family,)).fetchone()
            if not r:
                return None
            return ToolEvidencePattern(
                guidance_id=r["guidance_id"],
                vulnerability_family=r["vulnerability_family"],
                domain=r["domain"],
                primary_tools=json.loads(r["primary_tools"]),
                secondary_tools=json.loads(r["secondary_tools"]),
                required_evidence_artifacts=json.loads(r["required_evidence_artifacts"]),
                provenance=json.loads(r["provenance"])
            )

    # ── Human Feedback Records ────────────────────────────────────────────────

    def save_feedback(self, fb: FeedbackRecord) -> None:
        loc_json = json.dumps(fb.corrected_localization) if fb.corrected_localization else None
        query = """
        INSERT OR REPLACE INTO feedback_records (
            feedback_id, finding_id, hypothesis_reference, project_id, snapshot_id,
            analysis_unit_id, reviewer, label, reason, corrected_localization,
            corrected_security_property, corrected_attack_path,
            supporting_evidence_refs, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.get_connection() as conn:
            conn.execute(query, (
                fb.feedback_id,
                fb.finding_id,
                fb.hypothesis_reference,
                fb.project_id,
                fb.snapshot_id,
                fb.analysis_unit_id,
                fb.reviewer,
                fb.label.value,
                fb.reason,
                loc_json,
                fb.corrected_security_property,
                fb.corrected_attack_path,
                json.dumps(fb.supporting_evidence_refs),
                fb.created_at.isoformat()
            ))
            conn.commit()

    def list_feedback(self, project_id: Optional[str] = None, label: Optional[str] = None) -> List[FeedbackRecord]:
        query = "SELECT * FROM feedback_records"
        clauses = []
        params = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if label:
            clauses.append("label = ?")
            params.append(label)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC;"

        with self.db.get_connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [
                FeedbackRecord(
                    feedback_id=r["feedback_id"],
                    finding_id=r["finding_id"],
                    hypothesis_reference=r["hypothesis_reference"],
                    project_id=r["project_id"],
                    snapshot_id=r["snapshot_id"],
                    analysis_unit_id=r["analysis_unit_id"],
                    reviewer=r["reviewer"],
                    label=r["label"],
                    reason=r["reason"],
                    corrected_localization=json.loads(r["corrected_localization"]) if r["corrected_localization"] else None,
                    corrected_security_property=r["corrected_security_property"],
                    corrected_attack_path=r["corrected_attack_path"],
                    supporting_evidence_refs=json.loads(r["supporting_evidence_refs"]),
                    created_at=datetime.fromisoformat(r["created_at"])
                )
                for r in rows
            ]

    # ── Knowledge Promotions ──────────────────────────────────────────────────

    def save_promotion(self, prom: KnowledgePromotion) -> None:
        query = """
        INSERT OR REPLACE INTO knowledge_promotions (
            promotion_id, source_project_id, source_finding_id, proposed_pattern_id,
            accepted, rejection_reason, sanitized_fields, egress_policy_applied, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.get_connection() as conn:
            conn.execute(query, (
                prom.promotion_id,
                prom.source_project_id,
                prom.source_finding_id,
                prom.proposed_pattern_id,
                1 if prom.accepted else 0,
                prom.rejection_reason,
                json.dumps(prom.sanitized_fields),
                prom.egress_policy_applied.value,
                prom.created_at.isoformat()
            ))
            conn.commit()

    def get_promotion(self, promotion_id: str) -> Optional[KnowledgePromotion]:
        query = "SELECT * FROM knowledge_promotions WHERE promotion_id = ?;"
        with self.db.get_connection() as conn:
            r = conn.execute(query, (promotion_id,)).fetchone()
            if not r:
                return None
            return KnowledgePromotion(
                promotion_id=r["promotion_id"],
                source_project_id=r["source_project_id"],
                source_finding_id=r["source_finding_id"],
                proposed_pattern_id=r["proposed_pattern_id"],
                accepted=bool(r["accepted"]),
                rejection_reason=r["rejection_reason"],
                sanitized_fields=json.loads(r["sanitized_fields"]),
                egress_policy_applied=r["egress_policy_applied"],
                created_at=datetime.fromisoformat(r["created_at"])
            )
