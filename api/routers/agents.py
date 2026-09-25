"""
LLMorch API — Agents router (Phase 9.1).
GET /api/agents                 list all registered agents with runtime models & token metrics
GET /api/agents/{agent_id}        detail
GET /api/agents/{agent_id}/models list models compatible with agent
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional, Dict, Any, Union

from fastapi import APIRouter, Depends, HTTPException, Query

from api.models import (
    AgentSummary,
    ModelSummary,
    ModelCompatibilityItem,
    ModelDiagnosticItem,
    AgentModelsResponse,
    AgentRoleResponse,
    PaginatedResponse,
)
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

    from scheduler.execution_policy import get_execution_policy
    exec_policy = get_execution_policy()
    is_executable = exec_policy.is_agent_executable(aid)
    disabled_reason = exec_policy.get_agent_disabled_reason(aid)
    agent_status = "REGISTERED" if not is_executable else (row.get("status", "ACTIVE") or "ACTIVE")

    return AgentSummary(
        agent_id=aid,
        provider=row.get("provider", "unknown"),
        interface=row.get("interface", "CLI"),
        capabilities=caps,
        health=row.get("health", "UNKNOWN"),
        role=row.get("role", "general_analysis") or "general_analysis",
        status=agent_status,
        enabled=bool(row.get("enabled", 1)) and is_executable,
        executable=is_executable,
        execution_disabled_reason=disabled_reason,
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


@router.get("/{agent_id}/models", response_model=Union[AgentModelsResponse, List[ModelCompatibilityItem]])
def get_agent_models(
    agent_id: str,
    format: Optional[str] = Query(None, description="Optional format: 'list' or 'object' (default)"),
    session: SessionInfo = Depends(require_session)
):
    """
    Returns list of models supported and configured for the given agent.
    Provides authoritative compatibility information, active model resolution, and diagnostics.
    """
    db = _get_db()
    agent_row = None
    with db.get_connection() as conn:
        agent_row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()

    from registry.agent_registry import AgentRegistry
    from scheduler.execution_policy import get_execution_policy

    reg = AgentRegistry(populate_defaults=True)
    agent_obj = reg.get_agent(agent_id)

    if not agent_row and not agent_obj:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found in registry")

    agent_dict = dict(agent_row) if agent_row else {}
    provider = agent_dict.get("provider") or (agent_obj.provider if agent_obj else "unknown")

    exec_policy = get_execution_policy()
    is_executable = exec_policy.is_agent_executable(agent_id)
    disabled_reason = exec_policy.get_agent_disabled_reason(agent_id)

    # 1. Resolve current active model ID and validity status
    curr_model_id = (
        agent_dict.get("model")
        or agent_dict.get("current_model_id")
        or getattr(agent_obj, "current_model_id", None)
        or getattr(agent_obj, "model", None)
    )
    if not curr_model_id or curr_model_id == "runtime-resolved":
        def_m = _model_registry.get_default_model_for_agent(agent_id)
        curr_model_id = def_m.model_id if def_m else "runtime-resolved"

    curr_model_obj = _model_registry.get_model(curr_model_id) if curr_model_id else None
    if curr_model_obj:
        curr_model_status = "VALID" if curr_model_obj.enabled else "DISABLED"
    else:
        curr_model_status = "UNREGISTERED"

    # 2. Get compatible models
    models = _model_registry.get_models_for_agent(agent_id)
    if not models and agent_obj:
        # Fallback to provider-based matching if mappings weren't initialized
        models = _model_registry.list_models(provider=provider, enabled_only=True)

    compat_items = [
        ModelCompatibilityItem(
            model_id=m.model_id,
            display_name=m.display_name,
            provider=m.provider,
            context_window=m.context_window,
            max_output_tokens=m.max_output_tokens,
            capabilities=m.capabilities,
            available=m.enabled and is_executable,
            compatible=True,
            cost_per_million_input=m.cost_per_million_input,
            cost_per_million_output=m.cost_per_million_output,
            tier=m.metadata.get("tier"),
            rejection_reason=disabled_reason if not is_executable else None,
        )
        for m in models
    ]

    # 3. Compute diagnostic path for all candidate models in registry (Section 21)
    diagnostics = []
    all_models = _model_registry.list_models(enabled_only=False)
    for m in all_models:
        prov_match = (m.provider.lower() == provider.lower())
        is_compat = m in models
        rej_reason = None
        if "claude" in agent_id.lower() and not exec_policy.allow_real_claude_execution:
            rej_reason = "CLAUDE_RUNTIME_DISABLED"
        elif not is_executable:
            rej_reason = "AGENT_EXECUTION_DISABLED"
        elif not m.enabled:
            rej_reason = "MODEL_DISABLED"
        elif not prov_match:
            rej_reason = "PROVIDER_MISMATCH"
        elif not is_compat:
            rej_reason = "CAPABILITY_OR_BINDING_MISMATCH"

        diagnostics.append(ModelDiagnosticItem(
            model_id=m.model_id,
            registered=True,
            enabled=m.enabled,
            provider_match=prov_match,
            capability_match=is_compat,
            execution_allowed=is_executable,
            compatible=is_compat,
            rejection_reason=rej_reason,
        ))

    if format == "list":
        return compat_items

    return AgentModelsResponse(
        agent_id=agent_id,
        current_model_id=curr_model_id,
        current_model_status=curr_model_status,
        models=compat_items,
        supported_models=compat_items,
        diagnostics=diagnostics,
    )


@router.get("/{agent_id}/roles", response_model=AgentRoleResponse)
def get_agent_roles(
    agent_id: str,
    task_id: Optional[str] = Query(None),
    session: SessionInfo = Depends(require_session),
):
    """Returns available roles and the active role for an agent (optionally scoped to a task)."""
    db = _get_db()
    from history.phase9_repositories import AgentRoleRepository
    from registry.agent_registry import AgentRegistry, AVAILABLE_ROLES

    role_repo = AgentRoleRepository(db)
    active_role = role_repo.get_role(agent_id, task_id=task_id)

    return AgentRoleResponse(
        agent_id=agent_id,
        role=active_role,
        task_id=task_id,
        available_roles=AVAILABLE_ROLES,
        message=f"Active role for {agent_id} is '{active_role}'",
    )


@router.post("/{agent_id}/role", response_model=AgentRoleResponse)
async def change_agent_role(
    agent_id: str,
    request: AgentRoleChangeRequest,
    session: SessionInfo = Depends(require_session),
):
    """
    Changes the assigned role for an agent (globally or task-scoped).
    Creates an auditable event and broadcasts AGENT_ROLE_CHANGED over WebSocket.
    """
    db = _get_db()
    from history.phase9_repositories import AgentRoleRepository
    from registry.agent_registry import AVAILABLE_ROLES
    from api.events import event_manager

    if request.role not in AVAILABLE_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Role '{request.role}' is not in configured available roles: {AVAILABLE_ROLES}",
        )

    role_repo = AgentRoleRepository(db)
    assignment = role_repo.assign_role(
        agent_id=agent_id,
        role=request.role,
        task_id=request.task_id,
        assigned_by=session.role or "analyst",
        reason=request.reason,
    )

    # Broadcast realtime event
    await event_manager.broadcast(
        event_type="AGENT_ROLE_CHANGED",
        entity_type="agent",
        entity_id=agent_id,
        payload={
            "agent_id": agent_id,
            "role": request.role,
            "task_id": request.task_id,
            "assignment_id": assignment["assignment_id"],
            "reason": request.reason,
        },
    )

    return AgentRoleResponse(
        agent_id=agent_id,
        role=request.role,
        task_id=request.task_id,
        available_roles=AVAILABLE_ROLES,
        message=f"Successfully updated role for {agent_id} to '{request.role}'",
    )


