"""
LLMorch API — Settings & Configuration router (Phase 9.1).
Exposes analyst controls for agents, models, token budgets, execution, and security.
Safely masks server-side credentials and persists settings to SQLite.
"""

from __future__ import annotations

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from api.models import SettingsResponse, SettingsUpdateRequest
from api.session import require_session, SessionInfo
from api.realtime import event_manager
from history.database import get_db_path, DatabaseService
from history.repositories import ConfigurationRepository, EventRepository
from schemas.configuration import SystemSettings, AgentSettings, ModelSettings, ScopeSettings, ExecutionSettings, SecuritySettings
from schemas.token import TokenBudgetConfig
from schemas.event import Event, EventType

router = APIRouter(prefix="/api/settings", tags=["settings"])
config_alias_router = APIRouter(prefix="/api/config", tags=["config"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


def _mask_security(sec: SecuritySettings) -> Dict[str, Any]:
    """Ensures no raw API keys or sensitive material leave server memory."""
    res = sec.model_dump()
    # Mask any potential credential keys
    for provider, meta in res.get("credentials_status", {}).items():
        if isinstance(meta, dict) and "key" in meta:
            val = str(meta["key"])
            meta["masked"] = f"{val[:6]}••••••••" if len(val) > 8 else "••••••••"
            meta.pop("key", None)
    return res


def _get_settings_response(settings: SystemSettings) -> SettingsResponse:
    return SettingsResponse(
        settings_id=settings.settings_id,
        version=settings.version,
        agents=settings.agents.model_dump(),
        models=settings.models.model_dump(),
        tokens=settings.tokens.model_dump(),
        scope=settings.scope.model_dump(),
        execution=settings.execution.model_dump(),
        security=_mask_security(settings.security),
        updated_at=settings.updated_at,
    )


@router.get("", response_model=SettingsResponse)
def get_settings(session: SessionInfo = Depends(require_session)):
    db = _get_db()
    repo = ConfigurationRepository(db)
    settings = repo.get_settings()
    return _get_settings_response(settings)


@router.put("", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdateRequest,
    session: SessionInfo = Depends(require_session),
):
    db = _get_db()
    repo = ConfigurationRepository(db)
    current = repo.get_settings()

    # Backend Validation Rules
    if body.tokens:
        rb = body.tokens.get("run_budget")
        if rb is not None and rb < 0:
            raise HTTPException(status_code=400, detail="run_budget cannot be negative")
        low_t = body.tokens.get("low_threshold_percent")
        if low_t is not None and (low_t < 0 or low_t > 100):
            raise HTTPException(status_code=400, detail="low_threshold_percent must be between 0 and 100")

    if body.execution:
        conc = body.execution.get("concurrency")
        if conc is not None and conc < 1:
            raise HTTPException(status_code=400, detail="concurrency must be at least 1")
        retries = body.execution.get("retry_limit")
        if retries is not None and retries < 0:
            raise HTTPException(status_code=400, detail="retry_limit cannot be negative")

    # Update sections safely
    if body.agents:
        current.agents = AgentSettings(**{**current.agents.model_dump(), **body.agents})
    if body.models:
        current.models = ModelSettings(**{**current.models.model_dump(), **body.models})
    if body.tokens:
        current.tokens = TokenBudgetConfig(**{**current.tokens.model_dump(), **body.tokens})
    if body.scope:
        current.scope = ScopeSettings(**{**current.scope.model_dump(), **body.scope})
    if body.execution:
        current.execution = ExecutionSettings(**{**current.execution.model_dump(), **body.execution})

    current.version += 1
    current.updated_at = datetime.now(timezone.utc)

    saved = repo.save_settings(current, updated_by=session.session_id)

    # Emit audit event
    evt_repo = EventRepository(db)
    event_id = evt_repo.record(Event(
        event_type=EventType.RUN_CONFIGURATION_CHANGED,
        actor=session.session_id,
        payload={"new_version": saved.version, "updated_at": saved.updated_at.isoformat()}
    ))

    # Realtime notification
    await event_manager.broadcast(
        event_type="RUN_CONFIGURATION_CHANGED",
        entity_type="settings",
        entity_id=saved.settings_id,
        payload={"version": saved.version},
    )

    return _get_settings_response(saved)


# Route aliases on /api/config
@config_alias_router.get("", response_model=SettingsResponse)
def get_config(session: SessionInfo = Depends(require_session)):
    return get_settings(session)


@config_alias_router.put("", response_model=SettingsResponse)
async def update_config(
    body: SettingsUpdateRequest,
    session: SessionInfo = Depends(require_session),
):
    return await update_settings(body, session)
