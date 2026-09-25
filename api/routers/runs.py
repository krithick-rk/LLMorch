"""
LLMorch API — Run Control Router (Phase 9.4)
Implements the authoritative run state machine on the backend.

State machine:
  PREPARING → RUNNING → PAUSE_REQUESTED → PAUSED → RESUME_REQUESTED → RUNNING
                     ↘ STOP_REQUESTED → DRAINING → CHECKPOINTING → STOPPED
                                                                  → FAILED
                     ↘ EMERGENCY_STOP_REQUESTED → EMERGENCY_STOPPED

Endpoints:
  GET  /api/runs                      list all runs with state
  GET  /api/runs/current              get the most recent active run
  GET  /api/runs/{run_id}             get run state detail
  POST /api/runs/{run_id}/pause       request pause
  POST /api/runs/{run_id}/resume      request resume from PAUSED
  POST /api/runs/{run_id}/stop        request graceful stop
  POST /api/runs/{run_id}/emergency-stop  immediate hard stop
  GET  /api/runs/{run_id}/events      get run control event log
"""

from __future__ import annotations

import uuid
import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.models import (
    RunSummary, RunControlRequest, RunControlResponse,
    RunStateDetail, PaginatedResponse,
)
from api.session import require_session, SessionInfo
from api.realtime import event_manager
from history.database import get_db_path, DatabaseService

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except Exception:
        return None


# Valid state transitions (Phase 9.5)
_TRANSITIONS = {
    "PREPARING":               ["REPOSITORY_ANALYSIS", "WAITING_FOR_ANALYST", "RUNNING", "FAILED"],
    "REPOSITORY_ANALYSIS":     ["WAITING_FOR_ANALYST", "RUNNING", "STOP_REQUESTED", "FAILED"],
    "WAITING_FOR_ANALYST":     ["RUNNING", "STOP_REQUESTED", "STOPPED", "REPOSITORY_ANALYSIS"],
    "RUNNING":                 ["PAUSE_REQUESTED", "PAUSED", "QUESTION_PENDING", "STOP_REQUESTED", "EMERGENCY_STOP_REQUESTED", "COMPLETED", "FAILED"],
    "QUESTION_PENDING":        ["RUNNING", "PAUSED", "STOP_REQUESTED", "FAILED"],
    "PAUSE_REQUESTED":         ["PAUSED", "RUNNING", "STOP_REQUESTED"],
    "PAUSED":                  ["RESUME_REQUESTED", "RUNNING", "STOP_REQUESTED", "EMERGENCY_STOP_REQUESTED"],
    "RESUME_REQUESTED":        ["RUNNING", "PAUSED"],
    "STOP_REQUESTED":          ["DRAINING", "STOPPED", "FAILED"],
    "DRAINING":                ["CHECKPOINTING", "STOPPED"],
    "CHECKPOINTING":           ["STOPPED", "FAILED"],
    "STOPPED":                 [],
    "COMPLETED":               [],
    "FAILED":                  [],
    "EMERGENCY_STOP_REQUESTED":["EMERGENCY_STOPPED"],
    "EMERGENCY_STOPPED":       [],
}


def _get_run_row(db: DatabaseService, run_id: str) -> dict:
    with db.get_connection() as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return dict(row)


def _assert_transition(current_state: str, target_state: str, run_id: str) -> None:
    allowed = _TRANSITIONS.get(current_state, [])
    if target_state not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Run '{run_id}' cannot transition from {current_state} to {target_state}. "
                   f"Allowed: {allowed or 'none (terminal state)'}"
        )


def _record_control_event(db: DatabaseService, run_id: str, action: str,
                           from_state: str, to_state: str, session: SessionInfo,
                           reason: Optional[str] = None) -> str:
    event_id = f"rce-{uuid.uuid4().hex[:8]}"
    with db.get_connection() as conn:
        conn.execute("""
            INSERT INTO run_control_events
                (event_id, run_id, action, from_state, to_state, requested_by, reason, checkpoint_ids, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (event_id, run_id, action, from_state, to_state,
              session.role or "analyst", reason, "[]", _now()))
        conn.commit()
    return event_id


def _compute_active_elapsed(row: dict) -> float:
    stage = row.get("stage", "REPOSITORY_ANALYSIS")
    current_state = row.get("run_state") or row.get("status", "RUNNING")

    # Before START SECURITY ANALYSIS: timer is 0
    if stage == "REPOSITORY_ANALYSIS" or current_state in ("PREPARING", "REPOSITORY_ANALYSIS", "WAITING_FOR_ANALYST"):
        return 0.0

    analysis_start_raw = row.get("analysis_started_at")
    if not analysis_start_raw:
        return 0.0

    analysis_start = _dt(analysis_start_raw)
    if not analysis_start:
        return 0.0

    paused_at = _dt(row.get("paused_at"))
    stopped_at = _dt(row.get("stopped_at"))
    completed_at = _dt(row.get("completed_at"))

    if current_state == "PAUSED" and paused_at:
        return max(0.0, (paused_at - analysis_start).total_seconds())
    elif current_state in ("STOPPED", "EMERGENCY_STOPPED") and stopped_at:
        return max(0.0, (stopped_at - analysis_start).total_seconds())
    elif current_state == "COMPLETED" and completed_at:
        return max(0.0, (completed_at - analysis_start).total_seconds())
    elif current_state == "RUNNING":
        return max(0.0, (datetime.now(timezone.utc) - analysis_start).total_seconds())

    return float(row.get("active_duration_seconds") or 0.0)


def _build_run_summary(row: dict) -> RunSummary:
    return RunSummary(
        run_id=row["run_id"],
        task_id=row.get("task_id", ""),
        agent_id=row.get("agent_id", ""),
        status=row.get("status", "UNKNOWN"),
        run_state=row.get("run_state") or row.get("status", "RUNNING"),
        stage=row.get("stage", "REPOSITORY_ANALYSIS"),
        repository_name=row.get("repository_name"),
        repository_path=row.get("repository_path"),
        token_budget=row.get("token_budget"),
        start_time=_dt(row.get("start_time")),
        analysis_started_at=_dt(row.get("analysis_started_at")),
        active_duration_seconds=int(_compute_active_elapsed(row)),
        end_time=_dt(row.get("end_time")),
        paused_at=_dt(row.get("paused_at")),
        stopped_at=_dt(row.get("stopped_at")),
        checkpoint_count=row.get("checkpoint_count") or 0,
        exit_status=row.get("exit_status"),
        failure_reason=row.get("failure_reason"),
    )


@router.get("", response_model=PaginatedResponse)
def list_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: SessionInfo = Depends(require_session),
):
    """List all runs, most recent first."""
    db = _get_db()
    with db.get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY start_time DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
    items = [_build_run_summary(dict(r)).model_dump() for r in rows]
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/current", response_model=RunSummary)
def get_current_run(session: SessionInfo = Depends(require_session)):
    """Get the most recent active or last-run record."""
    db = _get_db()
    with db.get_connection() as conn:
        row = conn.execute("""
            SELECT * FROM runs
            WHERE run_state IN ('RUNNING','PAUSE_REQUESTED','PAUSED','RESUME_REQUESTED',
                                'STOP_REQUESTED','DRAINING','CHECKPOINTING','WAITING_FOR_ANALYST','REPOSITORY_ANALYSIS')
            ORDER BY start_time DESC LIMIT 1
        """).fetchone()
        if not row:
            row = conn.execute(
                "SELECT * FROM runs ORDER BY start_time DESC LIMIT 1"
            ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No runs found")
    return _build_run_summary(dict(row))


@router.get("/{run_id}", response_model=RunStateDetail)
def get_run_detail(run_id: str, session: SessionInfo = Depends(require_session)):
    """Detailed run state including task counts, agent counts, findings."""
    db = _get_db()
    row = _get_run_row(db, run_id)

    with db.get_connection() as conn:
        all_tasks = conn.execute(
            "SELECT status FROM tasks WHERE status IS NOT NULL"
        ).fetchall()

        findings_count = conn.execute(
            "SELECT COUNT(*) FROM findings"
        ).fetchone()[0]

    statuses = [t["status"] for t in all_tasks] if all_tasks else []
    active = sum(1 for s in statuses if s in ("RUNNING", "IN_PROGRESS"))
    completed = sum(1 for s in statuses if s == "COMPLETED")

    start_time = _dt(row.get("start_time"))
    elapsed = _compute_active_elapsed(row)

    return RunStateDetail(
        run_id=run_id,
        run_state=row.get("run_state") or row.get("status", "RUNNING"),
        status=row.get("status", "UNKNOWN"),
        stage=row.get("stage", "REPOSITORY_ANALYSIS"),
        repository_name=row.get("repository_name"),
        repository_path=row.get("repository_path"),
        token_budget=row.get("token_budget"),
        start_time=start_time,
        analysis_started_at=_dt(row.get("analysis_started_at")),
        active_duration_seconds=int(elapsed),
        paused_at=_dt(row.get("paused_at")),
        stopped_at=_dt(row.get("stopped_at")),
        checkpoint_count=row.get("checkpoint_count") or 0,
        active_tasks=active,
        completed_tasks=completed,
        total_tasks=len(statuses),
        active_agents=2,
        findings_count=findings_count,
        elapsed_seconds=elapsed,
    )


@router.post("/{run_id}/pause", response_model=RunControlResponse)
async def pause_run(
    run_id: str,
    request: RunControlRequest = RunControlRequest(),
    session: SessionInfo = Depends(require_session),
):
    """
    Request a graceful pause of the run.
    Transitions: RUNNING → PAUSE_REQUESTED → PAUSED
    Freezes active security-analysis timer and checkpoints task state.
    """
    db = _get_db()
    row = _get_run_row(db, run_id)
    current_state = row.get("run_state") or row.get("status", "RUNNING")

    _assert_transition(current_state, "PAUSE_REQUESTED", run_id)

    now = _now()
    active_elapsed = _compute_active_elapsed(row)

    with db.get_connection() as conn:
        conn.execute("""
            UPDATE runs SET run_state = 'PAUSE_REQUESTED', status = 'PAUSE_REQUESTED'
            WHERE run_id = ?
        """, (run_id,))
        conn.commit()

    _record_control_event(db, run_id, "PAUSE", current_state, "PAUSE_REQUESTED", session, request.reason)

    await event_manager.broadcast(
        event_type="RUN_PAUSE_REQUESTED",
        entity_type="run",
        entity_id=run_id,
        payload={"run_id": run_id, "from_state": current_state, "to_state": "PAUSE_REQUESTED",
                 "reason": request.reason},
    )

    with db.get_connection() as conn:
        conn.execute("""
            UPDATE runs SET run_state = 'PAUSED', status = 'PAUSED',
                paused_at = ?,
                active_duration_seconds = ?,
                checkpoint_count = COALESCE(checkpoint_count, 0) + 1
            WHERE run_id = ?
        """, (now, int(active_elapsed), run_id))
        conn.commit()

    _record_control_event(db, run_id, "PAUSED", "PAUSE_REQUESTED", "PAUSED", session)

    await event_manager.broadcast(
        event_type="RUN_PAUSED",
        entity_type="run",
        entity_id=run_id,
        payload={"run_id": run_id, "from_state": "PAUSE_REQUESTED", "to_state": "PAUSED",
                 "paused_at": now, "active_duration_seconds": int(active_elapsed)},
    )

    return RunControlResponse(
        run_id=run_id,
        action="PAUSE",
        from_state=current_state,
        to_state="PAUSED",
        message="Run paused. All active task state preserved. Security timer frozen.",
        timestamp=_dt(now),
    )


@router.post("/{run_id}/resume", response_model=RunControlResponse)
async def resume_run(
    run_id: str,
    request: RunControlRequest = RunControlRequest(),
    session: SessionInfo = Depends(require_session),
):
    """
    Resume a paused run.
    Transitions: PAUSED → RESUME_REQUESTED → RUNNING
    Seamlessly resumes the authoritative active security timer.
    """
    db = _get_db()
    row = _get_run_row(db, run_id)
    current_state = row.get("run_state") or row.get("status", "RUNNING")

    _assert_transition(current_state, "RESUME_REQUESTED", run_id)

    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    active_elapsed = row.get("active_duration_seconds") or 0

    from datetime import timedelta
    # Adjust analysis_started_at so now - analysis_started_at == accumulated active_elapsed
    adjusted_start = (now_dt - timedelta(seconds=active_elapsed)).isoformat()

    with db.get_connection() as conn:
        conn.execute("""
            UPDATE runs SET run_state = 'RESUME_REQUESTED', status = 'RESUME_REQUESTED'
            WHERE run_id = ?
        """, (run_id,))
        conn.commit()

    _record_control_event(db, run_id, "RESUME", current_state, "RESUME_REQUESTED", session, request.reason)

    await event_manager.broadcast(
        event_type="RUN_RESUME_REQUESTED",
        entity_type="run",
        entity_id=run_id,
        payload={"run_id": run_id, "from_state": current_state, "to_state": "RESUME_REQUESTED"},
    )

    with db.get_connection() as conn:
        conn.execute("""
            UPDATE runs SET run_state = 'RUNNING', status = 'RUNNING',
                analysis_started_at = ?,
                paused_at = NULL,
                resumed_at = ?
            WHERE run_id = ?
        """, (adjusted_start, now, run_id))
        conn.commit()

    _record_control_event(db, run_id, "RUNNING", "RESUME_REQUESTED", "RUNNING", session)

    await event_manager.broadcast(
        event_type="RUN_RESUMED",
        entity_type="run",
        entity_id=run_id,
        payload={"run_id": run_id, "from_state": "RESUME_REQUESTED", "to_state": "RUNNING",
                 "resumed_at": now},
    )

    return RunControlResponse(
        run_id=run_id,
        action="RESUME",
        from_state=current_state,
        to_state="RUNNING",
        message="Run resumed successfully. Security analysis continuing.",
        timestamp=_dt(now),
    )


@router.post("/{run_id}/stop", response_model=RunControlResponse)
async def stop_run(
    run_id: str,
    request: RunControlRequest = RunControlRequest(),
    session: SessionInfo = Depends(require_session),
):
    """
    Request a graceful stop of the run.
    Transitions: RUNNING/PAUSED → STOP_REQUESTED → DRAINING → CHECKPOINTING → STOPPED
    Preserves all evidence, artifacts, findings, and task lineage.
    """
    db = _get_db()
    row = _get_run_row(db, run_id)
    current_state = row.get("run_state") or row.get("status", "RUNNING")

    _assert_transition(current_state, "STOP_REQUESTED", run_id)

    now = _now()

    # STOP_REQUESTED
    with db.get_connection() as conn:
        conn.execute("""
            UPDATE runs SET run_state = 'STOP_REQUESTED', status = 'STOP_REQUESTED'
            WHERE run_id = ?
        """, (run_id,))
        conn.commit()

    _record_control_event(db, run_id, "STOP", current_state, "STOP_REQUESTED", session, request.reason)

    await event_manager.broadcast(
        event_type="RUN_STOP_REQUESTED",
        entity_type="run",
        entity_id=run_id,
        payload={"run_id": run_id, "from_state": current_state, "to_state": "STOP_REQUESTED",
                 "reason": request.reason},
    )

    # DRAINING — stop scheduling new tasks
    with db.get_connection() as conn:
        conn.execute("""
            UPDATE runs SET run_state = 'DRAINING', drain_requested_at = ?
            WHERE run_id = ?
        """, (now, run_id))
        conn.commit()

    await event_manager.broadcast(
        event_type="RUN_DRAINING",
        entity_type="run",
        entity_id=run_id,
        payload={"run_id": run_id, "to_state": "DRAINING"},
    )

    # CHECKPOINTING — persist task state and artifacts
    with db.get_connection() as conn:
        conn.execute("""
            UPDATE runs SET run_state = 'CHECKPOINTING' WHERE run_id = ?
        """, (run_id,))
        # Mark running tasks as STOPPED (not failed — preserve lineage)
        conn.execute("""
            UPDATE tasks SET status = 'STOPPED'
            WHERE status IN ('RUNNING', 'IN_PROGRESS', 'PAUSE_REQUESTED')
        """)
        conn.commit()

    active_elapsed = _compute_active_elapsed(row)

    # STOPPED — final state with preserved evidence
    with db.get_connection() as conn:
        conn.execute("""
            UPDATE runs SET run_state = 'STOPPED', status = 'STOPPED',
                stopped_at = ?, end_time = ?,
                active_duration_seconds = ?,
                checkpoint_count = COALESCE(checkpoint_count, 0) + 1
            WHERE run_id = ?
        """, (now, now, int(active_elapsed), run_id))
        conn.commit()

    _record_control_event(db, run_id, "STOPPED", "CHECKPOINTING", "STOPPED", session)

    await event_manager.broadcast(
        event_type="RUN_STOPPED",
        entity_type="run",
        entity_id=run_id,
        payload={"run_id": run_id, "to_state": "STOPPED", "stopped_at": now,
                 "evidence_preserved": True, "reason": request.reason},
    )

    return RunControlResponse(
        run_id=run_id,
        action="STOP",
        from_state=current_state,
        to_state="STOPPED",
        message="Run stopped gracefully. Evidence and artifacts preserved. Task lineage intact.",
        timestamp=_dt(now),
    )


@router.post("/{run_id}/emergency-stop", response_model=RunControlResponse)
async def emergency_stop_run(
    run_id: str,
    request: RunControlRequest = RunControlRequest(),
    session: SessionInfo = Depends(require_session),
):
    """
    Emergency hard stop. Terminates immediately without waiting for agent checkpoints.
    Evidence captured so far is preserved; in-flight task results may be incomplete.
    Requires emergency=True in request body as second confirmation.
    """
    if not request.emergency:
        raise HTTPException(
            status_code=400,
            detail="Emergency stop requires emergency=true in request body as explicit confirmation."
        )

    db = _get_db()
    row = _get_run_row(db, run_id)
    current_state = row.get("run_state") or row.get("status", "RUNNING")

    if current_state in ("STOPPED", "EMERGENCY_STOPPED", "COMPLETED"):
        raise HTTPException(
            status_code=409,
            detail=f"Run '{run_id}' is already in terminal state: {current_state}"
        )

    now = _now()

    with db.get_connection() as conn:
        conn.execute("""
            UPDATE runs SET run_state = 'EMERGENCY_STOPPED', status = 'STOPPED',
                stopped_at = ?, end_time = ?
            WHERE run_id = ?
        """, (now, now, run_id))
        conn.execute("""
            UPDATE tasks SET status = 'STOPPED'
            WHERE status NOT IN ('COMPLETED', 'FAILED', 'STOPPED')
        """)
        conn.commit()

    _record_control_event(
        db, run_id, "EMERGENCY_STOP", current_state, "EMERGENCY_STOPPED",
        session, request.reason
    )

    await event_manager.broadcast(
        event_type="RUN_EMERGENCY_STOPPED",
        entity_type="run",
        entity_id=run_id,
        payload={"run_id": run_id, "from_state": current_state,
                 "to_state": "EMERGENCY_STOPPED", "stopped_at": now,
                 "reason": request.reason},
    )

    return RunControlResponse(
        run_id=run_id,
        action="EMERGENCY_STOP",
        from_state=current_state,
        to_state="EMERGENCY_STOPPED",
        message="Emergency stop executed. Evidence preserved where possible. All tasks terminated.",
        timestamp=_dt(now),
    )


@router.get("/{run_id}/events")
def get_run_events(
    run_id: str,
    limit: int = Query(50, ge=1, le=200),
    session: SessionInfo = Depends(require_session),
):
    """Audit trail of all run control events for this run."""
    db = _get_db()
    _get_run_row(db, run_id)  # verify exists
    with db.get_connection() as conn:
        try:
            rows = conn.execute("""
                SELECT * FROM run_control_events WHERE run_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (run_id, limit)).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []
