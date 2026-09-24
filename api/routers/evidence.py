"""
LLMorch API — Evidence router.
GET /api/evidence              paginated list
GET /api/evidence/{evidence_id} detail
Evidence is read-only from the API. The browser cannot fabricate or update evidence.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.models import EvidenceSummary, EvidenceDetail, PaginatedResponse
from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

SECRET_FIELDS = {"api_key", "secret", "password", "token", "private_key", "credential"}


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


def _dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v))
    except Exception:
        return None


def _j(v):
    if not v:
        return {}
    try:
        return json.loads(v) if isinstance(v, str) else v
    except Exception:
        return {}


def _redact(d: dict) -> dict:
    """Remove known-sensitive keys from a provenance dict."""
    return {k: ("***REDACTED***" if k.lower() in SECRET_FIELDS else v) for k, v in d.items()}


def _row_to_summary(r: dict) -> EvidenceSummary:
    return EvidenceSummary(
        evidence_id=r["evidence_id"],
        finding_id=r.get("finding_id"),
        task_id=r.get("task_id"),
        source_tool=r.get("source_tool"),
        timestamp=_dt(r.get("timestamp")),
        raw_hash=r.get("raw_hash"),
        canonical_hash=r.get("canonical_hash"),
        semantic_identity=r.get("semantic_identity"),
    )


@router.get("", response_model=PaginatedResponse)
def list_evidence(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    finding_id: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    source_tool: Optional[str] = Query(None),
    session: SessionInfo = Depends(require_session),
):
    db = _get_db()
    with db.get_connection() as conn:
        filters = []
        params: list = []
        if finding_id:
            filters.append("finding_id = ?")
            params.append(finding_id)
        if task_id:
            filters.append("task_id = ?")
            params.append(task_id)
        if source_tool:
            filters.append("source_tool = ?")
            params.append(source_tool)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        total = conn.execute(f"SELECT COUNT(*) FROM evidence {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM evidence {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    items = [_row_to_summary(dict(r)).model_dump() for r in rows]
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/{evidence_id}", response_model=EvidenceDetail)
def get_evidence(evidence_id: str, session: SessionInfo = Depends(require_session)):
    db = _get_db()
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Evidence not found")
    r = dict(row)
    provenance = _j(r.get("provenance"))
    if isinstance(provenance, dict):
        provenance = _redact(provenance)
    return EvidenceDetail(
        evidence_id=r["evidence_id"],
        finding_id=r.get("finding_id"),
        task_id=r.get("task_id"),
        source_tool=r.get("source_tool"),
        timestamp=_dt(r.get("timestamp")),
        raw_hash=r.get("raw_hash"),
        canonical_hash=r.get("canonical_hash"),
        semantic_identity=r.get("semantic_identity"),
        tool_version=r.get("tool_version"),
        command=r.get("command"),
        stdout=r.get("stdout"),
        stderr=r.get("stderr"),
        exit_code=r.get("exit_code"),
        sandbox_id=r.get("sandbox_id"),
        environment_fingerprint=r.get("environment_fingerprint"),
        provenance=provenance if isinstance(provenance, dict) else {},
    )
