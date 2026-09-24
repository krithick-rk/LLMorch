"""
LLMorch API — Validation & Reproducer routers.
GET /api/validation/{validation_id}
GET /api/reproducers/{reproducer_id}
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.models import ValidationSummary, ReproducerSummary, PaginatedResponse
from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService

router = APIRouter(tags=["validation"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


def _dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v))
    except Exception:
        return None


@router.get("/api/validation", response_model=PaginatedResponse, tags=["validation"])
def list_validations(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    finding_id: Optional[str] = Query(None),
    verdict: Optional[str] = Query(None),
    session: SessionInfo = Depends(require_session),
):
    db = _get_db()
    with db.get_connection() as conn:
        filters = []
        params: list = []
        if finding_id:
            filters.append("finding_id = ?")
            params.append(finding_id)
        if verdict:
            filters.append("verdict = ?")
            params.append(verdict)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        total = conn.execute(f"SELECT COUNT(*) FROM validation_results {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM validation_results {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        items.append(ValidationSummary(
            validation_id=d.get("validation_id", ""),
            finding_id=d.get("finding_id"),
            reproducer_id=d.get("reproducer_id"),
            verdict=d.get("verdict", "INCONCLUSIVE"),
            validator_name=d.get("validator_name"),
            timestamp=_dt(d.get("timestamp")),
            replay_count=d.get("replay_count", 0) or 0,
            determinism=d.get("determinism"),
        ).model_dump())
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/api/validation/{validation_id}", response_model=ValidationSummary, tags=["validation"])
def get_validation(validation_id: str, session: SessionInfo = Depends(require_session)):
    db = _get_db()
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM validation_results WHERE validation_id = ?", (validation_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Validation result not found")
    d = dict(row)
    return ValidationSummary(
        validation_id=d.get("validation_id", ""),
        finding_id=d.get("finding_id"),
        reproducer_id=d.get("reproducer_id"),
        verdict=d.get("verdict", "INCONCLUSIVE"),
        validator_name=d.get("validator_name"),
        timestamp=_dt(d.get("timestamp")),
        replay_count=d.get("replay_count", 0) or 0,
        determinism=d.get("determinism"),
    )


@router.get("/api/reproducers", response_model=PaginatedResponse, tags=["reproducers"])
def list_reproducers(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    finding_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    session: SessionInfo = Depends(require_session),
):
    db = _get_db()
    with db.get_connection() as conn:
        filters = []
        params: list = []
        if finding_id:
            filters.append("finding_id = ?")
            params.append(finding_id)
        if status:
            filters.append("status = ?")
            params.append(status)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        total = conn.execute(f"SELECT COUNT(*) FROM reproducers {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM reproducers {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        items.append(ReproducerSummary(
            reproducer_id=d.get("reproducer_id", ""),
            finding_id=d.get("finding_id"),
            candidate_id=d.get("candidate_id"),
            status=d.get("status", "UNKNOWN"),
            manifest_hash=d.get("manifest_hash"),
            created_at=_dt(d.get("created_at")),
        ).model_dump())
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/api/reproducers/{reproducer_id}", response_model=ReproducerSummary, tags=["reproducers"])
def get_reproducer(reproducer_id: str, session: SessionInfo = Depends(require_session)):
    db = _get_db()
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM reproducers WHERE reproducer_id = ?", (reproducer_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Reproducer not found")
    d = dict(row)
    return ReproducerSummary(
        reproducer_id=d.get("reproducer_id", ""),
        finding_id=d.get("finding_id"),
        candidate_id=d.get("candidate_id"),
        status=d.get("status", "UNKNOWN"),
        manifest_hash=d.get("manifest_hash"),
        created_at=_dt(d.get("created_at")),
    )
