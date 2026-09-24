"""
LLMorch API — Findings router.
GET /api/findings              paginated list
GET /api/findings/{finding_id} detail
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.models import FindingSummary, FindingDetail, PaginatedResponse
from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService

router = APIRouter(prefix="/api/findings", tags=["findings"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


def _dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v))
    except Exception:
        return None


def _j(v, default=None):
    if not v:
        return default or []
    try:
        return json.loads(v) if isinstance(v, str) else v
    except Exception:
        return default or []


def _row_to_summary(row: dict) -> FindingSummary:
    return FindingSummary(
        finding_id=row["finding_id"],
        task_id=row.get("task_id"),
        hypothesis=row.get("hypothesis"),
        state=row.get("state", "OPEN"),
        severity=row.get("severity"),
        created_at=_dt(row.get("created_at")),
        updated_at=_dt(row.get("updated_at")),
    )


@router.get("", response_model=PaginatedResponse)
def list_findings(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    state: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    session: SessionInfo = Depends(require_session),
):
    db = _get_db()
    with db.get_connection() as conn:
        filters = []
        params: list = []
        if state:
            filters.append("state = ?")
            params.append(state)
        if task_id:
            filters.append("task_id = ?")
            params.append(task_id)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        total = conn.execute(f"SELECT COUNT(*) FROM findings {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM findings {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    items = [_row_to_summary(dict(r)).model_dump() for r in rows]
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/{finding_id}", response_model=FindingDetail)
def get_finding(finding_id: str, session: SessionInfo = Depends(require_session)):
    db = _get_db()
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM findings WHERE finding_id = ?", (finding_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Finding not found")
    r = dict(row)
    return FindingDetail(
        finding_id=r["finding_id"],
        task_id=r.get("task_id"),
        hypothesis=r.get("hypothesis"),
        state=r.get("state", "OPEN"),
        severity=r.get("severity"),
        created_at=_dt(r.get("created_at")),
        updated_at=_dt(r.get("updated_at")),
        evidence_ids=_j(r.get("evidence_ids")),
        artifact_ids=_j(r.get("artifact_ids")),
        affected_locations=_j(r.get("affected_locations")),
        confidence=r.get("confidence"),
        notes=r.get("notes"),
    )
