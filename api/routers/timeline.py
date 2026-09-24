"""
LLMorch API — Timeline router.
GET /api/timeline   chronological event stream with filters.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.models import TimelineEntry, PaginatedResponse
from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


def _dt(v):
    if not v:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(str(v))
    except Exception:
        return datetime.utcnow()


_READABLE = {
    "TASK_CREATED": "Task created",
    "TASK_STARTED": "Task started",
    "TASK_COMPLETED": "Task completed",
    "TASK_FAILED": "Task failed",
    "TASK_CANCELLED": "Task cancelled",
    "AGENT_STARTED": "Agent started",
    "AGENT_COMPLETED": "Agent completed",
    "AGENT_FAILED": "Agent failed",
    "TOOL_EXECUTED": "Tool executed",
    "HYPOTHESIS_CREATED": "Hypothesis created",
    "FINDING_STATE_CHANGED": "Finding state changed",
    "REPRODUCER_GENERATED": "Reproducer generated",
    "SANDBOX_STARTED": "Sandbox started",
    "SANDBOX_COMPLETED": "Sandbox completed",
    "VALIDATOR_STARTED": "Validator started",
    "VALIDATOR_COMPLETED": "Validator completed",
    "CHECKPOINT_CREATED": "Checkpoint created",
    "FAILOVER_INITIATED": "Failover initiated",
    "FAILOVER_COMPLETED": "Failover completed",
    "ANALYST_ACTION": "Analyst action",
    "FEEDBACK_SUBMITTED": "Feedback submitted",
}


def _row_to_entry(r: dict) -> TimelineEntry:
    evt_type = r.get("event_type", "UNKNOWN")
    payload_raw = r.get("payload", "{}")
    try:
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw or {}
    except Exception:
        payload = {}

    summary = _READABLE.get(evt_type, evt_type.replace("_", " ").title())
    # Enrich summary with payload context
    if "task_id" in payload:
        summary += f" — {payload['task_id'][:12]}"
    elif "agent_id" in payload:
        summary += f" — {payload['agent_id']}"

    return TimelineEntry(
        event_id=r.get("event_id", ""),
        event_type=evt_type,
        timestamp=_dt(r.get("timestamp")),
        actor=r.get("actor"),
        entity_type=r.get("entity_type"),
        entity_id=r.get("entity_id"),
        summary=summary,
        run_id=r.get("run_id"),
        task_id=r.get("task_id"),
    )


@router.get("", response_model=PaginatedResponse)
def get_timeline(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    run_id: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    since: Optional[str] = Query(None, description="ISO timestamp lower bound"),
    session: SessionInfo = Depends(require_session),
):
    db = _get_db()
    with db.get_connection() as conn:
        filters = []
        params: list = []
        if run_id:
            filters.append("run_id = ?")
            params.append(run_id)
        if task_id:
            filters.append("task_id = ?")
            params.append(task_id)
        if agent_id:
            filters.append("actor = ?")
            params.append(agent_id)
        if event_type:
            filters.append("event_type = ?")
            params.append(event_type)
        if since:
            filters.append("timestamp >= ?")
            params.append(since)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        total = conn.execute(f"SELECT COUNT(*) FROM events {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM events {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    items = [_row_to_entry(dict(r)).model_dump() for r in rows]
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)
