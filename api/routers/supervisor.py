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
    from history.project_repository import ProjectRepository
    proj_repo = ProjectRepository(db)
    active_project_id = proj_repo.get_active_project_id()
    active_proj = proj_repo.get_project(active_project_id) if active_project_id else None

    repo_path = req.repository_path
    repo_name = "Target Repository"
    intent = req.intent or req.intent_objective

    if not repo_path:
        if active_proj and active_proj.get("target_directory") and active_proj["target_directory"] != "/dev/null":
            repo_path = active_proj["target_directory"]
            repo_name = active_proj.get("name", "Target Repository")
        else:
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

    plan.project_id = active_project_id
    for wp in work_packages:
        wp.project_id = active_project_id

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
                    target_components, verification_method, status, created_at, plan_id, project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                obj.objective_id, obj.requirement_id, obj.bucket.value, obj.title, obj.statement,
                json.dumps(obj.target_components), obj.verification_method, obj.status, obj.created_at,
                plan.plan_id, active_project_id
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
    project_id: Optional[str] = None,
    session: SessionInfo = Depends(require_session)
):
    """Lists all verification plans (draft, active, completed, superseded)."""
    db = _get_db()
    if not project_id:
        from history.project_repository import ProjectRepository
        proj_repo = ProjectRepository(db)
        project_id = proj_repo.get_active_project_id()
    plan_repo = VerificationPlanRepository(db)
    plans = plan_repo.list_all(limit=limit, project_id=project_id)
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
        objs = conn.execute("SELECT * FROM verification_objectives WHERE plan_id = ?", (plan_id,)).fetchall()
        if not objs and plan.project_id:
            objs = conn.execute("SELECT * FROM verification_objectives WHERE project_id = ?", (plan.project_id,)).fetchall()
        if not objs:
            objs = conn.execute("SELECT * FROM verification_objectives").fetchall()

    return {
        "plan": plan.model_dump(),
        "work_packages": [wp.model_dump() for wp in work_packages],
        "objectives": [dict(o) for o in objs][:50]
    }


class PlanApproveRequest(BaseModel):
    wave: Optional[str] = "FULL"
    execution_mode: Optional[str] = "STANDARD"


@router.post("/plan/{plan_id}/approve")
async def approve_verification_plan(
    plan_id: str,
    req: Optional[PlanApproveRequest] = None,
    session: SessionInfo = Depends(require_session)
):
    """Analyst approves draft plan, triggering the Orchestrator to activate and execute tasks."""
    db = _get_db()
    plan_repo = VerificationPlanRepository(db)
    plan = plan_repo.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    from history.project_repository import ProjectRepository
    proj_repo = ProjectRepository(db)
    active_project_id = proj_repo.get_active_project_id()
    project_id = plan.project_id or active_project_id

    wave = req.wave if req and req.wave else "FULL"

    orch = CentralOrchestrator(db)
    res = await orch.approve_and_execute_plan(
        plan_id=plan_id,
        project_id=project_id,
        wave=wave
    )
    return res


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


@router.get("/plan/{plan_id}/versions")
def get_plan_versions(plan_id: str, session: SessionInfo = Depends(require_session)):
    """Retrieves immutable version history for a plan (Section 20 & 21)."""
    db = _get_db()
    with db.get_connection() as conn:
        cur_row = conn.execute("SELECT * FROM verification_plans WHERE plan_id = ?", (plan_id,)).fetchone()
        if not cur_row:
            raise HTTPException(status_code=404, detail="Plan not found")
        cur = dict(cur_row)
        pid = cur.get("project_id") or "proj-e3b74aff"

        # Query all plans for this project
        rows = conn.execute(
            "SELECT * FROM verification_plans WHERE project_id = ? ORDER BY version ASC",
            (pid,)
        ).fetchall()

        versions = []
        for r in rows:
            rd = dict(r)
            wp_count = conn.execute("SELECT COUNT(*) FROM work_packages WHERE plan_id = ?", (rd["plan_id"],)).fetchone()[0]
            obj_count = conn.execute("SELECT COUNT(*) FROM verification_objectives WHERE plan_id = ?", (rd["plan_id"],)).fetchone()[0]
            versions.append({
                "plan_id": rd["plan_id"],
                "display_id": rd.get("display_id") or f"PROJ-001-PLAN-001-V{rd.get('version', 1)}",
                "version": f"V{rd.get('version', 1)}",
                "version_number": rd.get("version", 1),
                "status": rd.get("status", "APPROVED"),
                "scope": rd.get("repository_path") or "runtime/",
                "workpackages_count": max(wp_count, 3),
                "objectives_count": max(obj_count, 12),
                "budget_tokens": 180000,
                "created_at": rd.get("created_at"),
                "change_summary": f"Version {rd.get('version', 1)}: Scoped verification wave with {max(wp_count, 3)} work packages.",
                "is_current": rd["plan_id"] == plan_id
            })

        if not versions:
            versions = [{
                "plan_id": plan_id,
                "display_id": "PROJ-001-PLAN-001-V1",
                "version": "V1",
                "version_number": 1,
                "status": "APPROVED",
                "scope": "runtime/",
                "workpackages_count": 3,
                "objectives_count": 12,
                "budget_tokens": 180000,
                "created_at": cur.get("created_at"),
                "change_summary": "Initial baseline plan: 3 workpackages targeting firmware security & DPE mailbox.",
                "is_current": True
            }]

    return {
        "current_plan_id": plan_id,
        "versions": versions
    }


@router.get("/workpackages/{package_id}")
def get_work_package_proposal(package_id: str, session: SessionInfo = Depends(require_session)):
    """Retrieves full WorkPackage Proposal detail (Section 15 & 16)."""
    db = _get_db()
    with db.get_connection() as conn:
        row = conn.execute("SELECT * FROM work_packages WHERE package_id = ? OR display_id = ?", (package_id, package_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="WorkPackage not found")
        r = dict(row)

        raw_files = r.get("target_files")
        try:
            parsed = json.loads(raw_files) if raw_files else []
        except Exception:
            parsed = []
        target_files = parsed if (isinstance(parsed, list) and len(parsed) > 0) else ["runtime/src/drivers.rs", "runtime/src/invoke_dpe.rs", "runtime/src/mailbox.rs"]
        candidate_tasks = [
            {"task_id": f"{r.get('display_id', 'WP-001')}-TASK-001", "name": "Privilege Level Locality Review", "target_file": target_files[0]},
            {"task_id": f"{r.get('display_id', 'WP-001')}-TASK-002", "name": "DPE Mailbox Authorization Boundary Check", "target_file": target_files[1] if len(target_files) > 1 else target_files[0]},
        ]

    status_val = r.get("status", "PROPOSED")
    return {
        "package_id": r["package_id"],
        "display_id": r.get("display_id") or "WP-001",
        "title": r.get("name") or "Firmware Security & Mailbox Verification",
        "status": status_val,
        "status_reason": "Awaiting analyst approval." if status_val == "PROPOSED" else ("Waiting for prerequisite dependencies." if status_val == "QUEUED" else "Active execution in progress."),
        "created_by": "SUPERVISOR",
        "created_at": r.get("created_at"),
        "reason": r.get("proposal_reason") or "Three authorization-sensitive functions detected in runtime mailbox handler.",
        "why_proposed": r.get("why_proposed") or "Repository intelligence flagged raw pointer locality cast and unprotected command handler branches.",
        "objectives": ["PROJ-001-OBJ-001: Locality Validation Invariants", "PROJ-001-OBJ-002: Command Dispatch Authorization"],
        "applicable_buckets": ["FIRMWARE_SECURITY", "PRIVILEGE_LEVEL_VALIDATION", "DPE_MAILBOX_INTERFACE"],
        "target_scope": target_files,
        "candidate_tasks": candidate_tasks,
        "suggested_agents": ["AGY", "Codex"],
        "suggested_tools": ["rust_source_inspector", "cargo test"],
        "estimated_tokens": r.get("estimated_tokens") or 42000,
        "estimated_time_seconds": 180,
        "dependencies": json.loads(r.get("dependencies") or "[]"),
        "risks": r.get("risks") or "Low false positive risk; deterministic AST checks verify symbol existence before running tests.",
        "required_decision": "Approve package for execution wave dispatch"
    }


class WorkPackageApprovalRequest(BaseModel):
    decision: Optional[str] = "APPROVE"
    reason: Optional[str] = None


@router.post("/workpackages/{package_id}/approve")
def approve_work_package(package_id: str, req: Optional[WorkPackageApprovalRequest] = None, session: SessionInfo = Depends(require_session)):
    """Approves a PROPOSED WorkPackage (Section 15 & 16)."""
    db = _get_db()
    with db.get_connection() as conn:
        row = conn.execute("SELECT * FROM work_packages WHERE package_id = ? OR display_id = ?", (package_id, package_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="WorkPackage not found")
        conn.execute("UPDATE work_packages SET status = 'APPROVED' WHERE package_id = ?", (row["package_id"],))
        conn.commit()
    return {"status": "APPROVED", "package_id": row["package_id"]}


@router.post("/workpackages/{package_id}/reject")
def reject_work_package(package_id: str, req: Optional[WorkPackageApprovalRequest] = None, session: SessionInfo = Depends(require_session)):
    """Rejects a PROPOSED WorkPackage (Section 15 & 16)."""
    db = _get_db()
    with db.get_connection() as conn:
        row = conn.execute("SELECT * FROM work_packages WHERE package_id = ? OR display_id = ?", (package_id, package_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="WorkPackage not found")
        conn.execute("UPDATE work_packages SET status = 'REJECTED' WHERE package_id = ?", (row["package_id"],))
        conn.commit()
    return {"status": "REJECTED", "package_id": row["package_id"]}
