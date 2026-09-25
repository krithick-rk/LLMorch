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
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.models import (
    SnapshotSummary,
    AnalysisUnitSummary,
    AnalysisUnitDetail,
    SecuritySurfaceSummary,
    PaginatedResponse,
    EstimateCostRequest,
    EstimateCostResponse,
    RepositoryValidateRequest,
    RepositoryValidateResponse,
    RepositorySelectRequest,
    RepositoryInfo,
    RepositorySelectResponse,
    CurrentRepositoryResponse,
    RecentRepositoryItem,
    RecentRepositoriesResponse,
    DirectoryEntry,
    DirectoryBrowseResponse,
)
from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService
from history.repositories import RepositoryEstimateRepository, EventRepository
from history.phase9_repositories import TargetRepositoryRepository
from configs.manager import ConfigManager
from repository_intelligence.intake import RepositoryIntake
from repository_intelligence.family import detect_repository_family
from repository_intelligence.token_estimator import estimate_repository_tokens
from api.realtime import event_manager
from schemas.event import Event, EventType

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


def _is_path_allowed(path_str: str) -> bool:
    try:
        resolved = Path(path_str).resolve()
        cfg = ConfigManager()
        sec = cfg.get_security_config()
        allowed = sec.get("allowed_repository_roots", [])
        if not allowed:
            return True
        for root in allowed:
            try:
                resolved_root = Path(root).resolve()
                resolved.relative_to(resolved_root)
                return True
            except ValueError:
                continue
        return False
    except Exception:
        return False


def _validate_repo_path(path_str: str) -> RepositoryValidateResponse:
    if not path_str or not path_str.strip():
        return RepositoryValidateResponse(
            valid=False,
            repository_path="",
            error="Repository path cannot be empty",
        )

    try:
        p = Path(path_str.strip()).expanduser().resolve()
    except Exception as e:
        return RepositoryValidateResponse(
            valid=False,
            repository_path=path_str,
            error=f"Invalid path format: {e}",
        )

    # Security root check
    if not _is_path_allowed(str(p)):
        return RepositoryValidateResponse(
            valid=False,
            repository_path=str(p),
            error=f"Path '{p}' is outside configured allowed repository roots",
        )

    # Exists check
    if not p.exists():
        return RepositoryValidateResponse(
            valid=False,
            repository_path=str(p),
            error=f"Directory '{p}' does not exist",
        )

    # Is directory check
    if not p.is_dir():
        return RepositoryValidateResponse(
            valid=False,
            repository_path=str(p),
            error=f"Target path '{p}' is a file, not a directory",
        )

    # Readable check
    if not os.access(p, os.R_OK):
        return RepositoryValidateResponse(
            valid=False,
            repository_path=str(p),
            error="Repository exists but is not readable by LLMorch server",
        )

    # Build / cache check
    if p.name in {".git", "node_modules", "__pycache__", "build", "dist", ".cache", ".pytest_cache"}:
        return RepositoryValidateResponse(
            valid=False,
            repository_path=str(p),
            error=f"Directory '{p.name}' is a build/cache directory, not a valid repository root",
        )

    try:
        intake = RepositoryIntake(str(p))
        snapshot = intake.create_snapshot()
        git_rev = intake.get_git_commit()
        family_type, _ = detect_repository_family(p)

        # Detect prominent languages
        lang_set = set()
        EXT_MAP = {
            ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++",
            ".sv": "SystemVerilog", ".v": "Verilog", ".vhdl": "VHDL",
            ".py": "Python", ".rs": "Rust", ".go": "Go",
            ".js": "JavaScript", ".ts": "TypeScript", ".json": "JSON",
            ".yaml": "YAML", ".yml": "YAML", ".sh": "Shell"
        }
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", "build", "dist", ".cache", ".venv"}]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in EXT_MAP:
                    lang_set.add(EXT_MAP[ext])
            if len(lang_set) >= 8:
                break

        return RepositoryValidateResponse(
            valid=True,
            repository_path=str(p),
            repository_name=p.name,
            repository_family=family_type.value,
            git_revision=git_rev,
            is_git=bool(git_rev),
            languages=sorted(list(lang_set)),
            file_count=snapshot.file_count,
            error=None,
        )
    except Exception as e:
        return RepositoryValidateResponse(
            valid=False,
            repository_path=str(p),
            error=f"Repository validation failed: {str(e)}",
        )


# ─── Phase 9.2: Target Repository Management ───────────────────────────────────

@router.post("/api/repositories/validate", response_model=RepositoryValidateResponse, tags=["repository"])
def validate_repository(
    request: RepositoryValidateRequest,
    session: SessionInfo = Depends(require_session),
):
    """Validates candidate target repository path against security boundaries and architecture."""
    return _validate_repo_path(request.repository_path)


@router.post("/api/repositories/select", response_model=RepositorySelectResponse, tags=["repository"])
async def select_repository(
    request: RepositorySelectRequest,
    session: SessionInfo = Depends(require_session),
):
    """Sets the authoritative Target / Attack Repository for the investigation."""
    v = _validate_repo_path(request.repository_path)
    if not v.valid:
        raise HTTPException(status_code=400, detail=v.error or "Invalid repository path")

    db = _get_db()
    target_repo = TargetRepositoryRepository(db)
    snapshot_id = f"snap-{uuid.uuid4().hex[:12]}"

    target_repo.save(
        repository_path=v.repository_path,
        repository_name=v.repository_name or Path(v.repository_path).name,
        repository_family=v.repository_family or "UNKNOWN",
        git_revision=v.git_revision,
        is_git=v.is_git,
        file_count=v.file_count,
        languages=v.languages,
        snapshot_id=snapshot_id,
        is_current=True,
    )

    # Record event in event repository
    try:
        ev_repo = EventRepository(db)
        ev_repo.record(Event(
            event_type=EventType.REPOSITORY_SNAPSHOT_CREATED,
            actor=f"analyst:{session.session_id[:8]}",
            payload={
                "repository_path": v.repository_path,
                "repository_name": v.repository_name,
                "repository_family": v.repository_family,
                "git_revision": v.git_revision,
                "snapshot_id": snapshot_id,
            }
        ))
    except Exception:
        pass

    # Realtime broadcast
    await event_manager.broadcast(
        event_type="REPOSITORY_SELECTED",
        entity_type="repository",
        entity_id=v.repository_path,
        payload={
            "repository_path": v.repository_path,
            "repository_name": v.repository_name,
            "repository_family": v.repository_family,
            "git_revision": v.git_revision,
            "snapshot_id": snapshot_id,
            "file_count": v.file_count,
            "languages": v.languages,
        }
    )

    info = RepositoryInfo(
        repository_path=v.repository_path,
        repository_name=v.repository_name or Path(v.repository_path).name,
        repository_family=v.repository_family or "UNKNOWN",
        git_revision=v.git_revision,
        is_git=v.is_git,
        languages=v.languages,
        file_count=v.file_count,
        snapshot_id=snapshot_id,
        status="VALIDATED",
        last_used=datetime.now(timezone.utc).isoformat(),
    )
    return RepositorySelectResponse(
        success=True,
        repository=info,
        message=f"Target repository '{info.repository_name}' successfully selected and validated",
    )


@router.get("/api/repositories/current", response_model=CurrentRepositoryResponse, tags=["repository"])
def get_current_repository(session: SessionInfo = Depends(require_session)):
    """Retrieves authoritative current Target / Attack Repository."""
    db = _get_db()
    target_repo = TargetRepositoryRepository(db)
    current = target_repo.get_current()
    if not current:
        cfg = ConfigManager()
        sys_repo = cfg.get_system_config().get("repository_root")
        if sys_repo and Path(sys_repo).exists() and Path(sys_repo).is_dir():
            v = _validate_repo_path(sys_repo)
            if v.valid:
                target_repo.save(
                    repository_path=v.repository_path,
                    repository_name=v.repository_name or Path(v.repository_path).name,
                    repository_family=v.repository_family or "UNKNOWN",
                    git_revision=v.git_revision,
                    is_git=v.is_git,
                    file_count=v.file_count,
                    languages=v.languages,
                    is_current=True,
                )
                current = target_repo.get_current()

    if not current:
        return CurrentRepositoryResponse(is_selected=False, repository=None)

    langs = current.get("languages", [])
    if isinstance(langs, str):
        try:
            langs = json.loads(langs)
        except Exception:
            langs = []

    return CurrentRepositoryResponse(
        is_selected=True,
        repository=RepositoryInfo(
            repository_path=current["repository_path"],
            repository_name=current.get("repository_name", Path(current["repository_path"]).name),
            repository_family=current.get("repository_family", "UNKNOWN"),
            git_revision=current.get("git_revision"),
            is_git=bool(current.get("is_git")),
            languages=langs,
            file_count=current.get("file_count", 0),
            snapshot_id=current.get("snapshot_id"),
            status="VALIDATED",
            last_used=current.get("last_used"),
        )
    )


@router.get("/api/repositories/recent", response_model=RecentRepositoriesResponse, tags=["repository"])
def list_recent_repositories(
    limit: int = Query(20, ge=1, le=50),
    session: SessionInfo = Depends(require_session),
):
    """Lists recently used target repositories."""
    db = _get_db()
    target_repo = TargetRepositoryRepository(db)
    rows = target_repo.list_recent(limit=limit)
    items = []
    for r in rows:
        path_exists = os.path.exists(r["repository_path"]) and os.path.isdir(r["repository_path"])
        langs = r.get("languages", [])
        if isinstance(langs, str):
            try:
                langs = json.loads(langs)
            except Exception:
                langs = []
        items.append(RecentRepositoryItem(
            repository_path=r["repository_path"],
            repository_name=r.get("repository_name", Path(r["repository_path"]).name),
            repository_family=r.get("repository_family", "UNKNOWN"),
            git_revision=r.get("git_revision"),
            is_git=bool(r.get("is_git")),
            file_count=r.get("file_count", 0),
            languages=langs,
            last_used=r.get("last_used", ""),
            is_available=path_exists,
        ))
    return RecentRepositoriesResponse(repositories=items)


@router.get("/api/repositories/browse", response_model=DirectoryBrowseResponse, tags=["repository"])
def browse_directory(
    path: Optional[str] = Query(None),
    session: SessionInfo = Depends(require_session),
):
    """
    Secure local directory navigator restricted to configured allowed roots.
    Never exposes file contents.
    """
    cfg = ConfigManager()
    sec = cfg.get_security_config()
    allowed_roots_raw = sec.get("allowed_repository_roots", [
        "/home/hackdac/Desktop",
        "/home/hackdac/Documents",
        "/tmp",
    ])
    allowed_roots = []
    for r in allowed_roots_raw:
        try:
            rp = Path(r).resolve()
            if rp.exists():
                allowed_roots.append(str(rp))
        except Exception:
            pass

    # If no path specified, list top allowed roots
    if not path or not path.strip():
        entries = []
        for ar in allowed_roots:
            p = Path(ar)
            entries.append(DirectoryEntry(
                name=p.name or str(p),
                path=str(p),
                is_dir=True,
                is_repository=(p / ".git").exists(),
                file_count=0,
            ))
        return DirectoryBrowseResponse(
            current_path="",
            parent_path=None,
            allowed_roots=allowed_roots,
            entries=entries,
        )

    # Validate target directory
    try:
        target = Path(path.strip()).expanduser().resolve()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid path format: {e}")

    # Check that target is under an allowed root
    matched_root = None
    for ar in allowed_roots:
        try:
            target.relative_to(ar)
            matched_root = ar
            break
        except ValueError:
            continue

    if not matched_root:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: Path '{target}' is outside configured allowed repository roots"
        )

    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail=f"Directory '{target}' not found")

    parent_path = None
    if str(target) != matched_root and str(target) != "/":
        parent_path = str(target.parent)

    entries = []
    try:
        for item in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if item.name.startswith(".") or item.name in {"node_modules", "__pycache__", "build", "dist", ".cache"}:
                continue
            is_directory = item.is_dir()
            # If symlink, ensure it does not escape allowed roots
            if item.is_symlink():
                try:
                    res_symlink = item.resolve()
                    symlink_allowed = any(
                        res_symlink == Path(ar) or str(res_symlink).startswith(str(Path(ar)) + "/")
                        for ar in allowed_roots
                    )
                    if not symlink_allowed:
                        continue
                    is_directory = res_symlink.is_dir()
                except Exception:
                    continue

            is_repo = False
            if is_directory:
                is_repo = (item / ".git").exists()

            entries.append(DirectoryEntry(
                name=item.name,
                path=str(item),
                is_dir=is_directory,
                is_repository=is_repo,
                file_count=0,
            ))
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied accessing directory '{target}'")

    return DirectoryBrowseResponse(
        current_path=str(target),
        parent_path=parent_path,
        allowed_roots=allowed_roots,
        entries=entries,
    )


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
    repo_path = request.repository_path
    if not repo_path:
        db = _get_db()
        target_repo = TargetRepositoryRepository(db)
        cur = target_repo.get_current()
        if cur:
            repo_path = cur["repository_path"]
        else:
            raise HTTPException(status_code=400, detail="Repository path is required or must be selected first")

    est = estimate_repository_tokens(
        repository_path=repo_path,
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

