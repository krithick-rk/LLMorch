"""
LLMorch API — Candidate Security Policies Router
Endpoints for querying, proposing, and reviewing candidate security policies (SoCureLLM-inspired).
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService
from policy.generator import PolicyGenerator
from schemas.soc_verification import PolicyCandidate, PolicyStatus


router = APIRouter(prefix="/api/policies", tags=["policies"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


class PolicyCreateRequest(BaseModel):
    title: str
    policy_rule: str
    domain: str = "SoC Security"
    threat_model_ref: Optional[str] = None
    supporting_evidence_ids: Optional[List[str]] = None


class PolicyReviewRequest(BaseModel):
    status: Optional[str] = None  # CANDIDATE, REVIEWED, APPROVED, WAIVED, REJECTED
    decision: Optional[str] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None


@router.get("")
def list_policies(
    status: Optional[str] = None,
    session: SessionInfo = Depends(require_session)
):
    """Lists candidate and reviewed security policies."""
    db = _get_db()
    generator = PolicyGenerator(db)
    policies = generator.list_policies(status=status)
    return {"policies": [p.model_dump() for p in policies], "total": len(policies)}


@router.post("")
def create_candidate_policy(
    req: PolicyCreateRequest,
    session: SessionInfo = Depends(require_session)
):
    """Proposes a new candidate policy with provenance. Does NOT modify the target repository."""
    db = _get_db()
    generator = PolicyGenerator(db)
    policy = generator.generate_candidate_policy(
        title=req.title,
        policy_rule=req.policy_rule,
        domain=req.domain,
        threat_model_ref=req.threat_model_ref,
        supporting_evidence_ids=req.supporting_evidence_ids
    )
    return {"status": "POLICY_PROPOSED", "policy": policy.model_dump()}


@router.post("/{policy_id}/review")
def review_policy_endpoint(
    policy_id: str,
    req: PolicyReviewRequest,
    session: SessionInfo = Depends(require_session)
):
    """Analyst reviews, approves, or waives a candidate security policy."""
    db = _get_db()
    generator = PolicyGenerator(db)
    status_str = req.decision or req.status or "REVIEWED"
    new_status = PolicyStatus(status_str) if status_str in [s.value for s in PolicyStatus] else PolicyStatus.REVIEWED
    generator.review_policy(policy_id, new_status)
    policy_dict = {
        "policy_id": policy_id,
        "status": new_status.value,
        "reviewed_by": req.reviewed_by,
        "review_notes": req.review_notes
    }
    return {
        "status": "REVIEW_RECORDED",
        "policy_id": policy_id,
        "new_status": new_status.value,
        "policy": policy_dict
    }
