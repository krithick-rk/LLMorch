"""
LLMorch API — Supervisor Router
Provides endpoints for verification plan generation, review, approval, rejection, and replanning.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService
from history.soc_repositories import (
    VerificationPlanRepository,
    WorkPackageRepository,
    SpecificationRepository,
    RequirementRepository,
)
from history.phase9_repositories import TargetRepositoryRepository
from supervisor.supervisor import Supervisor
from orchestrator.orchestrator import CentralOrchestrator
from repository_intelligence.preflight import analyze_repository_preflight
from schemas.soc_verification import PlanStatus, WorkPackageStatus


router = APIRouter(prefix="/api/supervisor", tags=["supervisor"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


class PlanGenerateRequest(BaseModel):
    repository_path: Optional[str] = None
    intent_objective: Optional[str] = None
    intent: Optional[str] = None
    spec_ids: Optional[List[str]] = None
    author: Optional[str] = None


class PlanReplanRequest(BaseModel):
    failed_package_id: Optional[str] = None
    failure_reason: Optional[str] = None
    reason: Optional[str] = None
    trigger: Optional[str] = None
    analyst_instruction: Optional[str] = None


@router.post("/plan")
def generate_verification_plan(
    req: PlanGenerateRequest,
    session: SessionInfo = Depends(require_session)
):
    """Supervisor synthesizes a draft VerificationPlan with 23-bucket mapping and work packages."""
    db = _get_db()
    repo_path = req.repository_path
    repo_name = "Target Repository"
    intent = req.intent or req.intent_objective

    if not repo_path:
        target_repo = TargetRepositoryRepository(db)
        cur = target_repo.get_current()
        if cur:
            repo_path = cur["repository_path"]
            repo_name = cur["repository_name"]
        else:
            raise HTTPException(status_code=400, detail="No repository specified or currently selected")

    p = Path(repo_path).resolve()
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=400, detail=f"Repository path '{repo_path}' is invalid or inaccessible")

    # Run preflight
    preflight = analyze_repository_preflight(str(p))

    # Fetch specifications & requirements if available
    req_repo = RequirementRepository(db)
    all_reqs = req_repo.list_all(limit=100)

    supervisor = Supervisor()
    plan, work_packages, objectives, questions = supervisor.synthesize_verification_plan(
        repository_path=str(p),
        repository_name=repo_name,
        intent_objective=intent,
        preflight=preflight,
        requirements=all_reqs
    )

    # Persist draft plan and proposed work packages
    plan_repo = VerificationPlanRepository(db)
    wp_repo = WorkPackageRepository(db)

    plan_repo.save(plan)
    for wp in work_packages:
        wp_repo.save(wp)

    with db.get_connection() as conn:
        for obj in objectives:
            conn.execute("""
                INSERT OR REPLACE INTO verification_objectives (
                    objective_id, requirement_id, bucket, title, statement,
                    target_components, verification_method, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                obj.objective_id, obj.requirement_id, obj.bucket.value, obj.title, obj.statement,
                json.dumps(obj.target_components), obj.verification_method, obj.status, obj.created_at
            ))
        conn.commit()

    return {
        "status": "PLAN_GENERATED",
        "plan": plan.model_dump(),
        "work_packages": [wp.model_dump() for wp in work_packages],
        "objectives_count": len(objectives),
        "proposed_questions": questions
    }


@router.get("/plans")
def list_verification_plans(
    limit: int = 50,
    session: SessionInfo = Depends(require_session)
):
    """Lists all verification plans (draft, active, completed, superseded)."""
    db = _get_db()
    plan_repo = VerificationPlanRepository(db)
    plans = plan_repo.list_all(limit=limit)
    return {"plans": [p.model_dump() for p in plans], "total": len(plans)}


@router.get("/plan/{plan_id}")
def get_verification_plan(
    plan_id: str,
    session: SessionInfo = Depends(require_session)
):
    """Retrieves full VerificationPlan details, including work packages and objectives."""
    db = _get_db()
    plan_repo = VerificationPlanRepository(db)
    wp_repo = WorkPackageRepository(db)

    plan = plan_repo.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    work_packages = wp_repo.list_for_plan(plan_id)
    with db.get_connection() as conn:
        objs = conn.execute("SELECT * FROM verification_objectives").fetchall()

    return {
        "plan": plan.model_dump(),
        "work_packages": [wp.model_dump() for wp in work_packages],
        "objectives": [dict(o) for o in objs][:50]
    }


@router.post("/plan/{plan_id}/approve")
def approve_verification_plan(
    plan_id: str,
    session: SessionInfo = Depends(require_session)
):
    """Analyst approves draft plan, triggering the Orchestrator to activate tasks."""
    db = _get_db()
    plan_repo = VerificationPlanRepository(db)
    plan = plan_repo.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan_repo.update_status(plan_id, PlanStatus.APPROVED, approved_by="analyst")
    orch = CentralOrchestrator(db)
    created_tasks = orch.activate_verification_plan(plan_id)

    return {
        "status": "PLAN_APPROVED_AND_ACTIVATED",
        "plan_id": plan_id,
        "activated_tasks": created_tasks,
        "message": f"VerificationPlan '{plan_id}' approved. Orchestrator spawned {len(created_tasks)} tasks."
    }


@router.post("/plan/{plan_id}/reject")
def reject_verification_plan(
    plan_id: str,
    session: SessionInfo = Depends(require_session)
):
    """Analyst rejects draft verification plan."""
    db = _get_db()
    plan_repo = VerificationPlanRepository(db)
    plan = plan_repo.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan_repo.update_status(plan_id, PlanStatus.REJECTED)
    return {"status": "PLAN_REJECTED", "plan_id": plan_id}


@router.post("/plan/{plan_id}/replan")
def replan_verification_plan(
    plan_id: str,
    req: PlanReplanRequest,
    session: SessionInfo = Depends(require_session)
):
    """Supervisor proposes a new plan version (v2, v3) in response to failure."""
    db = _get_db()
    plan_repo = VerificationPlanRepository(db)
    wp_repo = WorkPackageRepository(db)

    cur_plan = plan_repo.get(plan_id)
    if not cur_plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    failed_wp = wp_repo.get(req.failed_package_id)
    if not failed_wp:
        raise HTTPException(status_code=404, detail=f"WorkPackage '{req.failed_package_id}' not found")

    supervisor = Supervisor()
    new_plan, revised_wps = supervisor.propose_replan(
        current_plan=cur_plan,
        failed_work_package=failed_wp,
        failure_reason=req.failure_reason,
        analyst_instruction=req.analyst_instruction
    )

    plan_repo.save(new_plan)
    for wp in revised_wps:
        wp_repo.save(wp)

    return {
        "status": "REPLAN_PROPOSED",
        "parent_plan_id": plan_id,
        "new_plan": new_plan.model_dump(),
        "revised_work_packages": [wp.model_dump() for wp in revised_wps],
        "message": f"Supervisor generated revision v{new_plan.version} ({new_plan.plan_id}) for analyst review."
    }
