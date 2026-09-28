"""
LLMorch Candidate Policy Generation Plane (SoCureLLM-inspired)
Generates machine-readable security policy candidates with complete provenance.
Never automatically modifies repository files or silently enforces generated rules.
All policies remain CANDIDATE until reviewed and signed off by the analyst.
"""

from __future__ import annotations

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from history.database import DatabaseService
from schemas.soc_verification import PolicyCandidate, PolicyStatus


class PolicyGenerator:
    """
    Candidate Security Policy Generator.
    Produces verifiable policy rules from validated threat models, requirements, and evidence.
    """

    def __init__(self, db: Optional[DatabaseService] = None):
        self.db = db or DatabaseService()

    def generate_candidate_policy(
        self,
        title: str,
        policy_rule: str,
        domain: str = "SoC Security",
        threat_model_ref: Optional[str] = None,
        supporting_evidence_ids: Optional[List[str]] = None,
        author_role: str = "Policy Generation",
        provenance: str = "Automated policy extraction from validated evidence"
    ) -> PolicyCandidate:
        """
        Creates a new candidate policy record in SQLite.
        Does NOT modify the target repository.
        """
        policy_id = f"pol-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        evidence_list = supporting_evidence_ids or []

        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO policy_candidates (
                    policy_id, title, policy_rule, domain, threat_model_ref,
                    supporting_evidence_ids, status, author_role, provenance, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                policy_id, title, policy_rule, domain, threat_model_ref,
                str(evidence_list), PolicyStatus.CANDIDATE.value, author_role,
                provenance, now
            ))
            conn.commit()

        return PolicyCandidate(
            policy_id=policy_id,
            title=title,
            policy_rule=policy_rule,
            domain=domain,
            threat_model_ref=threat_model_ref,
            supporting_evidence_ids=evidence_list,
            status=PolicyStatus.CANDIDATE,
            author_role=author_role,
            provenance=provenance,
            created_at=now
        )

    def generate_policy(
        self,
        title: str,
        rule_expression: Optional[str] = None,
        policy_rule: Optional[str] = None,
        bucket: Optional[str] = None,
        domain: Optional[str] = "SoC Security",
        justification: Optional[str] = None,
        threat_model_ref: Optional[str] = None,
        supporting_evidence_ids: Optional[List[str]] = None,
        author_role: str = "Policy Generation",
        provenance: Optional[str] = None,
        **kwargs
    ) -> PolicyCandidate:
        """Alias for generate_candidate_policy accepting rule_expression and bucket."""
        rule = rule_expression or policy_rule or ""
        dom = bucket or domain or "SoC Security"
        prov = provenance or justification or "Automated policy extraction from validated evidence"
        return self.generate_candidate_policy(
            title=title,
            policy_rule=rule,
            domain=dom,
            threat_model_ref=threat_model_ref,
            supporting_evidence_ids=supporting_evidence_ids,
            author_role=author_role,
            provenance=prov
        )

    def list_policies(self, status: Optional[str] = None) -> List[PolicyCandidate]:
        with self.db.get_connection() as conn:
            if status:
                rows = conn.execute("SELECT * FROM policy_candidates WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM policy_candidates ORDER BY created_at DESC").fetchall()

            res = []
            for r in rows:
                d = dict(r)
                ev_ids = []
                try:
                    ev_ids = eval(d["supporting_evidence_ids"]) if d["supporting_evidence_ids"] else []
                except Exception:
                    ev_ids = []

                res.append(PolicyCandidate(
                    policy_id=d["policy_id"],
                    title=d["title"],
                    policy_rule=d["policy_rule"],
                    domain=d["domain"],
                    threat_model_ref=d["threat_model_ref"],
                    supporting_evidence_ids=ev_ids,
                    status=PolicyStatus(d["status"]),
                    author_role=d["author_role"],
                    provenance=d["provenance"],
                    created_at=d["created_at"]
                ))
            return res

    def review_policy(self, policy_id: str, new_status: PolicyStatus) -> None:
        """Analyst reviews, approves, or waives a candidate policy."""
        with self.db.get_connection() as conn:
            conn.execute("UPDATE policy_candidates SET status = ? WHERE policy_id = ?", (new_status.value, policy_id))
            conn.commit()
