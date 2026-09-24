"""
LLMorch API — Repository & Analysis Units router.
GET /api/repositories
GET /api/snapshots/{snapshot_id}
GET /api/analysis-units
GET /api/analysis-units/{unit_id}
GET /api/analysis-units/{unit_id}/security-surface
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.models import (
    SnapshotSummary,
    AnalysisUnitSummary,
    AnalysisUnitDetail,
    SecuritySurfaceSummary,
    PaginatedResponse,
    EstimateCostRequest,
    EstimateCostResponse,
)
from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService
from history.repositories import RepositoryEstimateRepository
from repository_intelligence.token_estimator import estimate_repository_tokens

router = APIRouter(tags=["repository"])


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
        return default if default is not None else []
    try:
        return json.loads(v) if isinstance(v, str) else v
    except Exception:
        return default if default is not None else []


# ─── Repositories / Snapshots ─────────────────────────────────────────────────

@router.get("/api/repositories", response_model=PaginatedResponse, tags=["repository"])
def list_snapshots(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: SessionInfo = Depends(require_session),
):
    db = _get_db()
    with db.get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM repository_snapshots").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM repository_snapshots ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        meta = _j(d.get("build_metadata"), {})
        items.append(SnapshotSummary(
            snapshot_id=d.get("snapshot_id", ""),
            repo_path=d.get("repo_path", ""),
            commit_hash=d.get("commit_hash"),
            branch=d.get("branch"),
            tag=d.get("tag"),
            created_at=_dt(d.get("created_at")),
            total_files=d.get("total_files", 0) or 0,
            family=d.get("family"),
        ).model_dump())
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/api/snapshots/{snapshot_id}", response_model=SnapshotSummary, tags=["repository"])
def get_snapshot(snapshot_id: str, session: SessionInfo = Depends(require_session)):
    db = _get_db()
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM repository_snapshots WHERE snapshot_id = ?", (snapshot_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    d = dict(row)
    return SnapshotSummary(
        snapshot_id=d.get("snapshot_id", ""),
        repo_path=d.get("repo_path", ""),
        commit_hash=d.get("commit_hash"),
        branch=d.get("branch"),
        tag=d.get("tag"),
        created_at=_dt(d.get("created_at")),
        total_files=d.get("total_files", 0) or 0,
        family=d.get("family"),
    )


# ─── Analysis Units ───────────────────────────────────────────────────────────

@router.get("/api/analysis-units", response_model=PaginatedResponse, tags=["analysis_units"])
def list_analysis_units(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    snapshot_id: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    security_critical: Optional[bool] = Query(None),
    session: SessionInfo = Depends(require_session),
):
    db = _get_db()
    with db.get_connection() as conn:
        filters = []
        params: list = []
        if snapshot_id:
            filters.append("snapshot_id = ?")
            params.append(snapshot_id)
        if domain:
            filters.append("domain = ?")
            params.append(domain)
        if priority:
            filters.append("priority = ?")
            params.append(priority)
        if security_critical is not None:
            filters.append("security_critical = ?")
            params.append(1 if security_critical else 0)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        total = conn.execute(f"SELECT COUNT(*) FROM analysis_units {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM analysis_units {where} ORDER BY priority DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        items.append(AnalysisUnitSummary(
            unit_id=d.get("unit_id", ""),
            name=d.get("name", ""),
            unit_type=d.get("unit_type", "UNKNOWN"),
            domain=d.get("domain", "UNKNOWN"),
            priority=d.get("priority", "MEDIUM"),
            snapshot_id=d.get("snapshot_id"),
            component_path=d.get("component_path"),
            security_critical=bool(d.get("security_critical", 0)),
        ).model_dump())
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/api/analysis-units/{unit_id}", response_model=AnalysisUnitDetail, tags=["analysis_units"])
def get_analysis_unit(unit_id: str, session: SessionInfo = Depends(require_session)):
    db = _get_db()
    try:
        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM analysis_units WHERE unit_id = ?", (unit_id,)
            ).fetchone()
    except Exception:
        row = None
    if not row:
        raise HTTPException(status_code=404, detail="AnalysisUnit not found")
    d = dict(row)
    return AnalysisUnitDetail(
        unit_id=d.get("unit_id", ""),
        name=d.get("name", ""),
        unit_type=d.get("unit_type", "UNKNOWN"),
        domain=d.get("domain", "UNKNOWN"),
        priority=d.get("priority", "MEDIUM"),
        snapshot_id=d.get("snapshot_id"),
        component_path=d.get("component_path"),
        security_critical=bool(d.get("security_critical", 0)),
        description=d.get("description"),
        rationale=d.get("rationale"),
        entry_points=_j(d.get("entry_points")),
        relevant_files=_j(d.get("relevant_files")),
        relevant_symbols=_j(d.get("relevant_symbols")),
        security_properties=_j(d.get("security_properties")),
        attack_paths=_j(d.get("attack_paths")),
    )



@router.get("/api/analysis-units/{unit_id}/security-surface", response_model=SecuritySurfaceSummary, tags=["security_surface"])
def get_security_surface(unit_id: str, session: SessionInfo = Depends(require_session)):
    db = _get_db()
    try:
        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM security_surfaces WHERE unit_id = ?", (unit_id,)
            ).fetchone()
    except Exception:
        row = None
    if not row:
        # Return empty surface rather than 404 — unit may exist but surface not yet computed
        return SecuritySurfaceSummary(
            surface_id=f"surface-{unit_id}",
            unit_id=unit_id,
        )
    d = dict(row)
    return SecuritySurfaceSummary(
        surface_id=d.get("surface_id", ""),
        unit_id=d.get("unit_id"),
        snapshot_id=d.get("snapshot_id"),
        entry_point_count=len(_j(d.get("entry_points"))),
        asset_count=len(_j(d.get("assets"))),
        boundary_count=len(_j(d.get("trust_boundaries"))),
        attacker_capability_count=len(_j(d.get("attacker_capabilities"))),
        countermeasure_count=len(_j(d.get("countermeasures"))),
    )


# ─── Phase 9.1: Repository Token Estimation ───────────────────────────────────

@router.post("/api/repository/estimate", response_model=EstimateCostResponse, tags=["estimation"])
def estimate_cost(
    request: EstimateCostRequest,
    session: SessionInfo = Depends(require_session),
):
    """
    Produces structured token estimate for repository security analysis before LLM dispatch.
    Differentiates repository footprint from LLM-scoped security tokens.
    Excludes quarantined secrets safely.
    """
    est = estimate_repository_tokens(
        repository_path=request.repository_path,
        selected_models=request.selected_models,
        analysis_policy=request.analysis_policy,
    )

    db = _get_db()
    repo = RepositoryEstimateRepository(db)
    saved = repo.save(est)

    return EstimateCostResponse(
        estimate_id=saved.estimate_id,
        repository_path=saved.repository_path,
        snapshot_id=saved.snapshot_id,
        total_files_discovered=saved.total_files_discovered,
        source_files_count=saved.source_files_count,
        security_relevant_files_count=saved.security_relevant_files_count,
        excluded_files_count=saved.excluded_files_count,
        quarantined_secrets_count=est.quarantined_secrets_count,
        raw_token_estimate=saved.raw_token_estimate,
        llm_scoped_token_estimate=saved.llm_scoped_token_estimate,
        analysis_unit_estimate=saved.analysis_unit_estimate,
        context_expansion_estimate=saved.context_expansion_estimate,
        initial_analysis_estimate=saved.initial_analysis_estimate,
        followup_analysis_estimate=saved.followup_analysis_estimate,
        estimated_total_tokens=saved.estimated_total_tokens,
        recommended_budget=saved.recommended_budget,
        estimation_method=saved.estimation_method.value,
        confidence=saved.confidence.value,
        confidence_rationale=saved.confidence_rationale,
        breakdown_by_language=[l.model_dump() for l in saved.breakdown_by_language],
        breakdown_by_stage=[s.model_dump() for s in saved.breakdown_by_stage],
        secrets_excluded_safely=saved.secrets_excluded_safely,
        created_at=saved.created_at,
    )


@router.get("/api/repository/estimate/{estimate_id}", response_model=EstimateCostResponse, tags=["estimation"])
def get_estimate(
    estimate_id: str,
    session: SessionInfo = Depends(require_session),
):
    db = _get_db()
    repo = RepositoryEstimateRepository(db)
    saved = repo.get(estimate_id)
    if not saved:
        raise HTTPException(status_code=404, detail="Estimate not found")

    return EstimateCostResponse(
        estimate_id=saved.estimate_id,
        repository_path=saved.repository_path,
        snapshot_id=saved.snapshot_id,
        total_files_discovered=saved.total_files_discovered,
        source_files_count=saved.source_files_count,
        security_relevant_files_count=saved.security_relevant_files_count,
        excluded_files_count=saved.excluded_files_count,
        quarantined_secrets_count=saved.quarantined_secrets_count,
        raw_token_estimate=saved.raw_token_estimate,
        llm_scoped_token_estimate=saved.llm_scoped_token_estimate,
        analysis_unit_estimate=saved.analysis_unit_estimate,
        context_expansion_estimate=saved.context_expansion_estimate,
        initial_analysis_estimate=saved.initial_analysis_estimate,
        followup_analysis_estimate=saved.followup_analysis_estimate,
        estimated_total_tokens=saved.estimated_total_tokens,
        recommended_budget=saved.recommended_budget,
        estimation_method=saved.estimation_method.value,
        confidence=saved.confidence.value,
        confidence_rationale=saved.confidence_rationale,
        breakdown_by_language=[l.model_dump() for l in saved.breakdown_by_language],
        breakdown_by_stage=[s.model_dump() for s in saved.breakdown_by_stage],
        secrets_excluded_safely=saved.secrets_excluded_safely,
        created_at=saved.created_at,
    )

