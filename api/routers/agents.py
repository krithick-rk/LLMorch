"""
LLMorch API — Agents router (Phase 9.1).
GET /api/agents                 list all registered agents with runtime models & token metrics
GET /api/agents/{agent_id}        detail
GET /api/agents/{agent_id}/models list models compatible with agent
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from api.models import AgentSummary, ModelSummary, PaginatedResponse
from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService
from registry.model_registry import ModelRegistry

router = APIRouter(prefix="/api/agents", tags=["agents"])
_model_registry = ModelRegistry()


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


def _row_to_agent(row: dict, conn: Any = None) -> AgentSummary:
    caps = _j(row.get("capabilities"))
    if not isinstance(caps, list):
        caps = []

    aid = row["agent_id"]
    supp_models = _j(row.get("supported_models"))
    if not supp_models:
        compat_models = _model_registry.get_models_for_agent(aid)
        supp_models = [m.model_id for m in compat_models]

    curr_model = row.get("current_model_id") or row.get("model")
    if not curr_model or curr_model == "runtime-resolved":
        def_m = _model_registry.get_default_model_for_agent(aid)
        curr_model = def_m.model_id if def_m else (supp_models[0] if supp_models else "runtime-resolved")

    tokens_used = 0
    token_limit = None
    tokens_remaining = None
    switch_count = 0
    failover_count = 0
    current_task_id = None
    current_task_objective = None

    if conn:
        try:
            tok_row = conn.execute(
                "SELECT SUM(total_tokens_actual) as act, SUM(total_tokens_estimated) as est FROM token_usage WHERE agent_id = ?",
                (aid,)
            ).fetchone()
            if tok_row:
                tokens_used = (tok_row["act"] or 0) if (tok_row["act"] or 0) > 0 else (tok_row["est"] or 0)

            bgt_row = conn.execute(
                "SELECT budget_limit, remaining FROM token_budgets WHERE scope_type = 'agent' AND scope_id = ?",
                (aid,)
            ).fetchone()
            if bgt_row:
                token_limit = bgt_row["budget_limit"]
                tokens_remaining = bgt_row["remaining"]
            else:
                token_limit = 150000
                tokens_remaining = max(0, token_limit - tokens_used)

            sw_row = conn.execute(
                "SELECT COUNT(*) FROM agent_switches WHERE new_agent_id = ? AND switch_type = 'MANUAL'",
                (aid,)
            ).fetchone()
            if sw_row:
                switch_count = sw_row[0]

            fo_row = conn.execute(
                "SELECT COUNT(*) FROM agent_switches WHERE previous_agent_id = ? AND switch_type = 'FAILOVER'",
                (aid,)
            ).fetchone()
            if fo_row:
                failover_count = fo_row[0]

            task_row = conn.execute(
                "SELECT task_id, objective FROM tasks WHERE assigned_agent_id = ? AND status IN ('RUNNING', 'DISPATCHED') LIMIT 1",
                (aid,)
            ).fetchone()
            if task_row:
                current_task_id = task_row["task_id"]
                current_task_objective = task_row["objective"]
        except Exception:
            pass

    return AgentSummary(
        agent_id=aid,
        provider=row.get("provider", "unknown"),
        interface=row.get("interface", "CLI"),
        capabilities=caps,
        health=row.get("health", "UNKNOWN"),
        role=row.get("role", "general_analysis") or "general_analysis",
        status=row.get("status", "ACTIVE") or "ACTIVE",
        enabled=bool(row.get("enabled", 1)),
        current_model_id=curr_model,
        supported_models=supp_models,
        current_task_id=current_task_id,
        current_task_objective=current_task_objective,
        tokens_used=tokens_used,
        token_limit=token_limit,
        tokens_remaining=tokens_remaining,
        failover_count=failover_count,
        switch_count=switch_count,
        registered_at=_dt(row.get("registered_at")),
    )


@router.get("", response_model=PaginatedResponse)
def list_agents(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    health: Optional[str] = Query(None),
    session: SessionInfo = Depends(require_session),
):
    db = _get_db()
    with db.get_connection() as conn:
        filters = []
        params: list = []
        if health:
            filters.append("health = ?")
            params.append(health)

        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        total = conn.execute(f"SELECT COUNT(*) FROM agents {where}", params).fetchone()[0]
        if total == 0 and not filters:
            from registry.agent_registry import AgentRegistry
            reg = AgentRegistry(populate_defaults=True)
            for a in reg.list_agents():
                conn.execute("""
                    INSERT OR IGNORE INTO agents (
                        agent_id, provider, interface, model, capabilities, protocols,
                        permissions, health, availability, concurrency_limit, usage_status,
                        quota_status, workspace_class, auth_profile, adapter_version,
                        metadata, schema_version, role, status, enabled, supported_models,
                        current_model_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    a.agent_id, a.provider, a.interface.value, a.model, json.dumps(a.capabilities),
                    json.dumps(a.protocols), json.dumps(a.permissions), a.health.value, 1 if a.availability else 0,
                    a.concurrency_limit, a.usage_status.model_dump_json(), a.quota_status.value,
                    a.workspace_class, json.dumps(a.auth_profile), a.adapter_version,
                    json.dumps(a.metadata), a.schema_version, a.role, a.status, 1 if a.enabled else 0,
                    json.dumps(a.supported_models), a.current_model_id
                ))
            conn.commit()
            total = conn.execute(f"SELECT COUNT(*) FROM agents {where}", params).fetchone()[0]

        rows = conn.execute(
            f"SELECT * FROM agents {where} ORDER BY registered_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        items = [_row_to_agent(dict(r), conn=conn).model_dump() for r in rows]

    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/{agent_id}", response_model=AgentSummary)
def get_agent(agent_id: str, session: SessionInfo = Depends(require_session)):
    db = _get_db()
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found")
        return _row_to_agent(dict(row), conn=conn)


@router.get("/{agent_id}/models", response_model=List[ModelSummary])
def get_agent_models(agent_id: str, session: SessionInfo = Depends(require_session)):
    """Returns list of models supported and configured for the given agent."""
    models = _model_registry.get_models_for_agent(agent_id)
    return [
        ModelSummary(
            model_id=m.model_id,
            provider=m.provider,
            display_name=m.display_name,
            context_window=m.context_window,
            max_output_tokens=m.max_output_tokens,
            input_token_tracking_supported=m.input_token_tracking_supported,
            output_token_tracking_supported=m.output_token_tracking_supported,
            token_estimation_method=m.token_estimation_method.value,
            capabilities=m.capabilities,
            enabled=m.enabled,
            cost_per_million_input=m.cost_per_million_input,
            cost_per_million_output=m.cost_per_million_output,
        )
        for m in models
    ]
