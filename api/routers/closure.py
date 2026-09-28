"""
LLMorch API — Closure & Coverage Router
Endpoints for querying closure snapshots, requirement coverage matrices, open gaps, and waivers.
"""

from __future__ import annotations

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService
from history.soc_repositories import VerificationPlanRepository, ClosureRepository
from closure.engine import ClosureEngine
from schemas.soc_verification import CoverageState, GapSeverity
from schemas.soc_ontology import SoCBucket


router = APIRouter(prefix="/api/closure", tags=["closure"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


class WaiverRequest(BaseModel):
    plan_id: Optional[str] = None
    bucket: Optional[str] = "security"
    requirement_id: Optional[str] = None
    objective_id: Optional[str] = None
    waiver_reason: Optional[str] = None
    justification: Optional[str] = None
    approved_by: Optional[str] = None


class RecordGapRequest(BaseModel):
    plan_id: Optional[str] = None
    bucket: Optional[str] = "security"
    title: str
    description: str
    severity: str = "MEDIUM"
    requirement_id: Optional[str] = None
    recommended_action: str = "Investigate further"


@router.get("")
def get_project_closure(
    project_id: Optional[str] = None,
    session: SessionInfo = Depends(require_session)
):
    """Retrieves project-scoped closure snapshot or clean 0% state for new projects."""
    db = _get_db()
    from history.project_repository import ProjectRepository
    proj_repo = ProjectRepository(db)
    target_project_id = project_id or proj_repo.get_active_project_id()

    with db.get_connection() as conn:
        plan_row = conn.execute(
            "SELECT plan_id FROM verification_plans WHERE project_id = ? ORDER BY version DESC, created_at DESC LIMIT 1",
            (target_project_id,)
        ).fetchone()

    if not plan_row:
        return {
            "snapshot": {
                "snapshot_id": "snap-empty",
                "plan_id": None,
                "requirement_coverage_pct": 0.0,
                "objective_coverage_pct": 0.0,
                "total_requirements": 0,
                "covered_requirements": 0,
                "total_objectives": 0,
                "covered_objectives": 0,
                "open_gaps_count": 0,
                "waivers_count": 0,
                "evidence_items_count": 0,
                "is_closed": False,
            },
            "coverage_items": [],
            "open_gaps": [],
            "waivers": []
        }
    return get_closure_snapshot(plan_row["plan_id"], session=session)


@router.get("/{plan_id}")
def get_closure_snapshot(
    plan_id: str,
    session: SessionInfo = Depends(require_session)
):
    """Retrieves authoritative closure snapshot and coverage metrics for a plan."""
    db = _get_db()
    engine = ClosureEngine(db)
    try:
        snap = engine.evaluate_closure(plan_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    with db.get_connection() as conn:
        cov_items = conn.execute("SELECT * FROM coverage_items WHERE plan_id = ?", (plan_id,)).fetchall()
        gaps = conn.execute("SELECT * FROM gaps WHERE plan_id = ?", (plan_id,)).fetchall()

    return {
        "snapshot": snap.model_dump(),
        "coverage_items": [dict(c) for c in cov_items],
        "open_gaps": [dict(g) for g in gaps if g["status"] == "OPEN"],
        "waivers": [dict(c) for c in cov_items if c["coverage_state"] == CoverageState.WAIVED.value]
    }


@router.post("/waiver")
@router.post("/{plan_id}/waiver")
def record_waiver(
    req: WaiverRequest,
    plan_id: Optional[str] = None,
    session: SessionInfo = Depends(require_session)
):
    """Records an analyst-authorized waiver for an objective or requirement."""
    db = _get_db()
    engine = ClosureEngine(db)
    target_plan_id = plan_id or req.plan_id or "default-plan"
    soc_bucket = SoCBucket(req.bucket) if req.bucket in [b.value for b in SoCBucket] else SoCBucket.SECURITY
    reason = req.waiver_reason or req.justification or "Analyst waiver"

    item = engine.record_coverage(
        plan_id=target_plan_id,
        bucket=soc_bucket,
        requirement_id=req.requirement_id,
        objective_id=req.objective_id,
        coverage_state=CoverageState.WAIVED,
        evidence_ids=[],
        waiver_reason=reason
    )
    return {"status": "WAIVER_RECORDED", "coverage_item": item.model_dump()}


@router.post("/gap")
@router.post("/{plan_id}/gap")
def record_gap_endpoint(
    req: RecordGapRequest,
    plan_id: Optional[str] = None,
    session: SessionInfo = Depends(require_session)
):
    """Records an identified verification gap."""
    db = _get_db()
    engine = ClosureEngine(db)
    target_plan_id = plan_id or req.plan_id or "default-plan"
    soc_bucket = SoCBucket(req.bucket) if req.bucket in [b.value for b in SoCBucket] else SoCBucket.SECURITY
    severity = GapSeverity(req.severity) if req.severity in [s.value for s in GapSeverity] else GapSeverity.MEDIUM

    gap = engine.record_gap(
        plan_id=target_plan_id,
        bucket=soc_bucket,
        title=req.title,
        description=req.description,
        severity=severity,
        requirement_id=req.requirement_id,
        recommended_action=req.recommended_action
    )
    return {"status": "GAP_RECORDED", "gap": gap.model_dump()}
