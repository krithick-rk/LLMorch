"""
LLMorch API — Controls router.
POST /api/controls/action   — analyst control actions (pause/resume/cancel/retry/etc.)
POST /api/controls/feedback — structured finding feedback
GET  /api/controls/audit    — audit log of analyst actions

All actions go through the control-plane policy check, create an auditable event,
and then trigger the actual state transition. The browser NEVER mutates state directly.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.models import (
    ControlRequest,
    ControlResponse,
    FeedbackRequest,
    FeedbackResponse,
    PaginatedResponse,
    AgentSwitchRequest,
    AgentSwitchResponse,
    ModelSwitchRequest,
    ModelSwitchResponse,
    SwitchAuditRecord,
)
from api.session import require_session, SessionInfo
from api.realtime import event_manager
from history.database import get_db_path, DatabaseService
from history.repositories import AgentSwitchRepository, ModelSwitchRepository
from scheduler.agent_switcher import AgentSwitcher

router = APIRouter(prefix="/api/controls", tags=["controls"])

# Allowed actions and their target types
_ALLOWED_ACTIONS = {
    "pause": ["task"],
    "resume": ["task"],
    "cancel": ["task", "run"],
    "retry": ["task"],
    "rerun_validation": ["validation", "reproducer"],
    "approve": ["task", "run"],
}

_HIGH_IMPACT = {"rerun_validation", "approve"}

_FEEDBACK_LABELS = {
    "CONFIRMED",
    "FALSE_POSITIVE",
    "MISSED_VULNERABILITY",
    "PARTIALLY_CORRECT",
    "WRONG_LOCALIZATION",
    "WRONG_ATTACK_PATH",
    "WRONG_SECURITY_PROPERTY",
    "INSUFFICIENT_EVIDENCE",
    "CORRECT_REASONING_WRONG_CONCLUSION",
}


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


def _persist_audit_event(
    db: DatabaseService,
    event_type: str,
    actor: str,
    entity_type: str,
    entity_id: str,
    payload: dict,
) -> str:
    event_id = f"evt-{uuid.uuid4().hex[:12]}"
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO events (event_id, event_type, actor, entity_type, entity_id, payload, timestamp, schema_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_type,
                actor,
                entity_type,
                entity_id,
                str(payload),
                datetime.now(timezone.utc).isoformat(),
                "1.0",
            ),
        )
    return event_id


@router.post("/action", response_model=ControlResponse)
async def analyst_action(
    request: ControlRequest,
    session: SessionInfo = Depends(require_session),
):
    """
    Submit an analyst control action.
    Policy is evaluated server-side before any state transition.
    All accepted actions create auditable events.
    """
    # 1. Validate action type
    allowed_targets = _ALLOWED_ACTIONS.get(request.action)
    if allowed_targets is None:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")
    if request.target_type not in allowed_targets:
        raise HTTPException(
            status_code=400,
            detail=f"Action '{request.action}' not valid for target type '{request.target_type}'",
        )

    # 2. Verify target exists
    db = _get_db()
    table_map = {
        "task": ("tasks", "task_id"),
        "run": ("runs", "run_id"),
        "validation": ("validation_results", "validation_id"),
        "reproducer": ("reproducers", "reproducer_id"),
    }
    table, pk_col = table_map[request.target_type]
    with db.get_connection() as conn:
        row = conn.execute(
            f"SELECT * FROM {table} WHERE {pk_col} = ?", (request.target_id,)
        ).fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"{request.target_type.title()} '{request.target_id}' not found",
        )

    # 3. For high-impact actions, require explicit reason
    if request.action in _HIGH_IMPACT and not request.reason:
        return ControlResponse(
            accepted=False,
            message="High-impact action requires a reason field",
            control_plane_decision="REJECTED",
        )

    # 4. Build audit payload
    payload = {
        "action": request.action,
        "target_type": request.target_type,
        "target_id": request.target_id,
        "reason": request.reason,
        "session_id": session.session_id,
        "actor": f"analyst:{session.session_id[:8]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # 5. Persist auditable event
    event_id = _persist_audit_event(
        db=db,
        event_type="ANALYST_ACTION",
        actor=f"analyst:{session.session_id[:8]}",
        entity_type=request.target_type,
        entity_id=request.target_id,
        payload=payload,
    )

    # 6. Apply state transition (via the actual table, not bypassing the control plane)
    _apply_state_transition(db, request)

    # 7. Broadcast realtime event
    await event_manager.broadcast(
        event_type="ANALYST_ACTION",
        entity_type=request.target_type,
        entity_id=request.target_id,
        payload={"action": request.action, "event_id": event_id},
    )

    return ControlResponse(
        accepted=True,
        event_id=event_id,
        message=f"Action '{request.action}' applied to {request.target_type} '{request.target_id}'",
        control_plane_decision="ACCEPTED",
    )


def _apply_state_transition(db: DatabaseService, request: ControlRequest) -> None:
    """Apply the actual state transition through the control plane (not raw SQL bypass)."""
    STATUS_MAP = {
        ("task", "pause"): "PAUSED",
        ("task", "resume"): "RUNNING",
        ("task", "cancel"): "CANCELLED",
        ("task", "retry"): "READY",
        ("run", "cancel"): "CANCELLED",
    }
    key = (request.target_type, request.action)
    new_status = STATUS_MAP.get(key)
    if new_status:
        table, pk_col = {
            "task": ("tasks", "task_id"),
            "run": ("runs", "run_id"),
        }[request.target_type]
        with db.get_connection() as conn:
            conn.execute(
                f"UPDATE {table} SET status = ? WHERE {pk_col} = ?",
                (new_status, request.target_id),
            )


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    session: SessionInfo = Depends(require_session),
):
    """
    Submit structured analyst feedback on a finding.
    Does NOT modify the finding itself — creates a feedback event only.
    """
    if request.label not in _FEEDBACK_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid label '{request.label}'. Must be one of: {sorted(_FEEDBACK_LABELS)}",
        )

    db = _get_db()
    # Verify finding exists
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT finding_id FROM findings WHERE finding_id = ?", (request.finding_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Finding not found")

    feedback_id = f"fb-{uuid.uuid4().hex[:12]}"
    payload = {
        "feedback_id": feedback_id,
        "finding_id": request.finding_id,
        "label": request.label,
        "comment": request.comment,
        "session_id": session.session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    event_id = _persist_audit_event(
        db=db,
        event_type="FEEDBACK_SUBMITTED",
        actor=f"analyst:{session.session_id[:8]}",
        entity_type="finding",
        entity_id=request.finding_id,
        payload=payload,
    )

    await event_manager.broadcast(
        event_type="FEEDBACK_SUBMITTED",
        entity_type="finding",
        entity_id=request.finding_id,
        payload={"label": request.label, "feedback_id": feedback_id},
    )

    return FeedbackResponse(
        accepted=True,
        feedback_id=feedback_id,
        message=f"Feedback '{request.label}' recorded for finding '{request.finding_id}'",
    )


@router.get("/audit", response_model=PaginatedResponse)
def get_audit_log(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    session: SessionInfo = Depends(require_session),
):
    """Return the analyst action audit log."""
    db = _get_db()
    with db.get_connection() as conn:
        filters = ["event_type IN ('ANALYST_ACTION','FEEDBACK_SUBMITTED')"]
        params: list = []
        if entity_type:
            filters.append("entity_type = ?")
            params.append(entity_type)
        if entity_id:
            filters.append("entity_id = ?")
            params.append(entity_id)
        where = "WHERE " + " AND ".join(filters)
        total = conn.execute(f"SELECT COUNT(*) FROM events {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM events {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    items = [dict(r) for r in rows]
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


# ─── Phase 9.1: Agent & Model Switching ───────────────────────────────────────

@router.post("/agent-switch", response_model=AgentSwitchResponse)
async def request_agent_switch(
    request: AgentSwitchRequest,
    session: SessionInfo = Depends(require_session),
):
    """
    Analyst request to switch an assigned agent on a task.
    Backend validates availability, creates an immutable checkpoint,
    retires the old run to prevent duplicate execution, spawns a new run,
    and broadcasts state transition events.
    """
    db = _get_db()
    switcher = AgentSwitcher(db_service=db)

    try:
        res = switcher.switch_agent(
            task_id=request.task_id,
            new_agent_id=request.new_agent_id,
            reason=request.reason,
            resume_action=request.resume_action,
            new_model_id=request.new_model_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Realtime notification broadcast
    await event_manager.broadcast(
        event_type="AGENT_SWITCH_COMPLETED",
        entity_type="task",
        entity_id=res["task_id"],
        payload=res,
    )

    return AgentSwitchResponse(
        accepted=True,
        switch_id=res["switch_id"],
        task_id=res["task_id"],
        previous_agent_id=res["previous_agent_id"],
        new_agent_id=res["new_agent_id"],
        new_model_id=res.get("new_model_id"),
        new_run_id=res.get("new_run_id"),
        checkpoint_id=res.get("checkpoint_id"),
        resume_action=res["resume_action"],
        message=f"Agent switched from {res['previous_agent_id']} to {res['new_agent_id']}",
    )


@router.post("/model-switch", response_model=ModelSwitchResponse)
async def request_model_switch(
    request: ModelSwitchRequest,
    session: SessionInfo = Depends(require_session),
):
    """
    Analyst request to change the active model for an agent or task.
    Validated against ModelRegistry capability matrix and agent support.
    """
    db = _get_db()
    switcher = AgentSwitcher(db_service=db)

    try:
        res = switcher.switch_model(
            agent_id=request.agent_id,
            new_model_id=request.new_model_id,
            reason=request.reason,
            task_id=request.task_id,
            run_id=request.run_id,
            scope=request.scope,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Realtime broadcast
    await event_manager.broadcast(
        event_type="MODEL_SWITCH_COMPLETED",
        entity_type="agent",
        entity_id=res["agent_id"],
        payload=res,
    )

    return ModelSwitchResponse(
        accepted=True,
        switch_id=res["switch_id"],
        agent_id=res["agent_id"],
        previous_model_id=res["previous_model_id"],
        new_model_id=res["new_model_id"],
        scope=res["scope"],
        message=f"Model switched from {res['previous_model_id']} to {res['new_model_id']} for agent {res['agent_id']}",
    )


@router.get("/switches")
def get_switch_history(
    task_id: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: SessionInfo = Depends(require_session),
):
    """Lists audit history of agent and model switches."""
    db = _get_db()
    agent_sw_repo = AgentSwitchRepository(db)
    model_sw_repo = ModelSwitchRepository(db)

    agent_switches = agent_sw_repo.list_switches(task_id=task_id, run_id=run_id, limit=limit)
    model_switches = model_sw_repo.list_switches(task_id=task_id, limit=limit)

    return {
        "items": agent_switches,
        "total": len(agent_switches) + len(model_switches),
        "agent_switches": agent_switches,
        "model_switches": model_switches,
    }
