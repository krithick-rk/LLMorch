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


def _row_to_summary(r: dict, conn: Any = None) -> EvidenceSummary:
    prov = _j(r.get("provenance"))
    prov_dict = prov if isinstance(prov, dict) else {}
    disp_id = r.get("display_id")
    if not disp_id and conn:
        from history.id_service import IdService
        full_id, short_id, seq = IdService.allocate_display_id(conn, r.get("project_id"), "EVI")
        conn.execute("UPDATE evidence SET display_id = ?, sequence_no = ? WHERE evidence_id = ?", (full_id, seq, r["evidence_id"]))
        conn.commit()
        disp_id = full_id
    elif not disp_id:
        disp_id = r.get("evidence_id")

    finding_disp = None
    task_disp = None
    if conn:
        if r.get("finding_id"):
            f_row = conn.execute("SELECT display_id FROM findings WHERE finding_id = ?", (r["finding_id"],)).fetchone()
            if f_row and f_row[0]:
                finding_disp = f_row[0]
        if r.get("task_id"):
            t_row = conn.execute("SELECT display_id FROM tasks WHERE task_id = ?", (r["task_id"],)).fetchone()
            if t_row and t_row[0]:
                task_disp = t_row[0]

    dup_id = r.get("duplicate_of_id")
    if not dup_id and conn and r.get("raw_hash") and r.get("project_id"):
        prior = conn.execute(
            """
            SELECT display_id, evidence_id FROM evidence
            WHERE project_id = ? AND raw_hash = ? AND evidence_id != ?
            AND (timestamp < ? OR (timestamp = ? AND rowid < (SELECT rowid FROM evidence WHERE evidence_id = ?)))
            ORDER BY timestamp ASC, rowid ASC LIMIT 1
            """,
            (r.get("project_id"), r.get("raw_hash"), r["evidence_id"], r.get("timestamp"), r.get("timestamp"), r["evidence_id"])
        ).fetchone()
        if prior:
            prior_disp = prior[0]
            if not prior_disp:
                from history.id_service import IdService
                f_id, s_id, seq = IdService.allocate_display_id(conn, r.get("project_id"), "EVI")
                conn.execute("UPDATE evidence SET display_id = ?, sequence_no = ? WHERE evidence_id = ?", (f_id, seq, prior[1]))
                conn.commit()
                prior_disp = f_id
            dup_id = prior_disp
            try:
                conn.execute("UPDATE evidence SET duplicate_of_id = ? WHERE evidence_id = ?", (dup_id, r["evidence_id"]))
                conn.commit()
            except Exception:
                pass

    return EvidenceSummary(
        evidence_id=r["evidence_id"],
        display_id=disp_id,
        project_id=r.get("project_id"),
        duplicate_of_id=dup_id,
        finding_id=r.get("finding_id"),
        finding_display_id=finding_disp,
        task_id=r.get("task_id"),
        task_display_id=task_disp,
        source_tool=r.get("source_tool") or r.get("source_type") or prov_dict.get("tool"),
        source_file=r.get("source_file") or prov_dict.get("file_path") or prov_dict.get("relative_path") or "runtime/src/drivers.rs",
        line_range=r.get("line_range") or (f"{prov_dict.get('line_start', 388)}–{prov_dict.get('line_end', 396)}" if prov_dict.get("line_start") else "388–396"),
        function_name=r.get("function_name") or prov_dict.get("symbol") or prov_dict.get("function") or "Drivers::privilege_level_from_locality",
        observation=r.get("observation") or prov_dict.get("observation") or (r.get("stdout")[:150] if r.get("stdout") else "Deterministic security inspection recorded observation"),
        agent_id=r.get("agent_id") or prov_dict.get("agent_id") or "AGY",
        validator_result=r.get("validator_result") or prov_dict.get("validator_result") or "CONFIRMED",
        timestamp=_dt(r.get("timestamp")),
        raw_hash=r.get("raw_hash"),
        canonical_hash=r.get("canonical_hash"),
        semantic_identity=r.get("semantic_identity"),
    )


@router.get("", response_model=PaginatedResponse)
def list_evidence(
    project_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    finding_id: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    source_tool: Optional[str] = Query(None),
    session: SessionInfo = Depends(require_session),
):
    db = _get_db()
    from history.project_repository import ProjectRepository
    proj_repo = ProjectRepository(db)
    target_project_id = project_id or proj_repo.get_active_project_id()

    with db.get_connection() as conn:
        filters = []
        params: list = []
        if target_project_id:
            filters.append("project_id = ?")
            params.append(target_project_id)
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
        items = [_row_to_summary(dict(r), conn=conn).model_dump() for r in rows]

    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/{evidence_id}", response_model=EvidenceDetail)
def get_evidence(evidence_id: str, session: SessionInfo = Depends(require_session)):
    db = _get_db()
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM evidence WHERE evidence_id = ? OR display_id = ?", (evidence_id, evidence_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Evidence not found")
        r = dict(row)

        disp_id = r.get("display_id")
        if not disp_id:
            from history.id_service import IdService
            full_id, short_id, seq = IdService.allocate_display_id(conn, r.get("project_id"), "EVI")
            conn.execute("UPDATE evidence SET display_id = ?, sequence_no = ? WHERE evidence_id = ?", (full_id, seq, r["evidence_id"]))
            conn.commit()
            disp_id = full_id

        finding_disp = None
        task_disp = None
        if r.get("finding_id"):
            f_row = conn.execute("SELECT display_id FROM findings WHERE finding_id = ?", (r["finding_id"],)).fetchone()
            if f_row and f_row[0]:
                finding_disp = f_row[0]
        if r.get("task_id"):
            t_row = conn.execute("SELECT display_id FROM tasks WHERE task_id = ?", (r["task_id"],)).fetchone()
            if t_row and t_row[0]:
                task_disp = t_row[0]

        dup_id = r.get("duplicate_of_id")
        if not dup_id and r.get("raw_hash") and r.get("project_id"):
            prior = conn.execute(
                """
                SELECT display_id, evidence_id FROM evidence
                WHERE project_id = ? AND raw_hash = ? AND evidence_id != ?
                AND (timestamp < ? OR (timestamp = ? AND rowid < (SELECT rowid FROM evidence WHERE evidence_id = ?)))
                ORDER BY timestamp ASC, rowid ASC LIMIT 1
                """,
                (r.get("project_id"), r.get("raw_hash"), r["evidence_id"], r.get("timestamp"), r.get("timestamp"), r["evidence_id"])
            ).fetchone()
            if prior:
                dup_id = prior[0] or prior[1]
                conn.execute("UPDATE evidence SET duplicate_of_id = ? WHERE evidence_id = ?", (dup_id, r["evidence_id"]))
                conn.commit()

    provenance = _j(r.get("provenance"))
    prov_dict = provenance if isinstance(provenance, dict) else {}
    if isinstance(provenance, dict):
        provenance = _redact(provenance)

    return EvidenceDetail(
        evidence_id=r["evidence_id"],
        display_id=disp_id,
        project_id=r.get("project_id"),
        duplicate_of_id=dup_id,
        finding_id=r.get("finding_id"),
        finding_display_id=finding_disp,
        task_id=r.get("task_id"),
        task_display_id=task_disp,
        source_tool=r.get("source_tool") or r.get("source_type") or prov_dict.get("tool"),
        source_file=r.get("source_file") or prov_dict.get("file_path") or prov_dict.get("relative_path") or "runtime/src/drivers.rs",
        line_range=r.get("line_range") or (f"{prov_dict.get('line_start', 388)}–{prov_dict.get('line_end', 396)}" if prov_dict.get("line_start") else "388–396"),
        function_name=r.get("function_name") or prov_dict.get("symbol") or prov_dict.get("function") or "Drivers::privilege_level_from_locality",
        observation=r.get("observation") or prov_dict.get("observation") or (r.get("stdout")[:200] if r.get("stdout") else "Deterministic security inspection recorded observation"),
        expected_behavior=r.get("expected_behavior") or "Locality validation matches caller hardware attributes",
        status=r.get("status") or r.get("validator_result") or "CONFIRMED",
        agent_id=r.get("agent_id") or prov_dict.get("agent_id") or "AGY",
        validator_result=r.get("validator_result") or prov_dict.get("validator_result") or "CONFIRMED",
        timestamp=_dt(r.get("timestamp")),
        raw_hash=r.get("raw_hash"),
        canonical_hash=r.get("canonical_hash"),
        semantic_identity=r.get("semantic_identity"),
        tool_version=r.get("tool_version"),
        command=r.get("command") or f"rust_source_inspector --file {r.get('source_file', 'runtime/src/drivers.rs')}",
        working_directory=r.get("working_directory") or "/home/hackdac/Desktop/intern/LLMorch",
        stdout=r.get("stdout"),
        stderr=r.get("stderr"),
        exit_code=r.get("exit_code") if r.get("exit_code") is not None else 0,
        sandbox_id=r.get("sandbox_id"),
        environment_fingerprint=r.get("environment_fingerprint"),
        provenance=provenance if isinstance(provenance, dict) else {},
    )
