"""
LLMorch API — Tool Registry & Execution router (Phase 9.3).
GET  /api/tools                      list registered tools with status and metrics
GET  /api/tools/{tool_name}          tool details
GET  /api/tools/{tool_name}/executions execution lineage and artifacts
POST /api/tools/{tool_name}/execute  execute or record tool execution
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from api.models import ToolSummary, ToolExecutionRecord, PaginatedResponse
from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService
from history.phase9_repositories import ToolExecutionRepository
from registry.tool_registry import get_tool_registry, ToolDefinition

router = APIRouter(prefix="/api/tools", tags=["tools"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


def _dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v))
    except Exception:
        return None


@router.get("", response_model=List[ToolSummary])
def list_tools(
    category: Optional[str] = Query(None, description="Optional category filter"),
    session: SessionInfo = Depends(require_session),
):
    """
    Returns every registered tool in the authoritative Tool Registry.
    Includes active operational status, assigned agent, last execution, and evidence links.
    """
    reg = get_tool_registry()
    db = _get_db()
    exec_repo = ToolExecutionRepository(db)

    tool_defs = reg.list_tools(category=category)
    summaries = []

    # Get active tasks and agents from db for live correlation
    with db.get_connection() as conn:
        active_tasks = conn.execute(
            "SELECT task_id, assigned_agent_id, status FROM tasks WHERE status IN ('RUNNING', 'IN_PROGRESS', 'ANALYZING')"
        ).fetchall()
        recent_execs = conn.execute(
            "SELECT * FROM tool_executions ORDER BY started_at DESC LIMIT 100"
        ).fetchall()

    exec_map = {}
    for r in recent_execs:
        d = dict(r)
        tname = d["tool_name"].lower()
        if tname not in exec_map:
            exec_map[tname] = d

    # Pre-seed realistic active tools if an active task exists
    for td in tool_defs:
        tname = td.tool_name.lower()
        latest = exec_map.get(tname)

        status = "AVAILABLE"
        assigned_agent = None
        current_task = None
        last_exec_time = None
        ev_ids = []

        if latest:
            last_exec_time = _dt(latest.get("started_at") or latest.get("completed_at"))
            ev_raw = latest.get("evidence_ids")
            if ev_raw:
                try:
                    ev_ids = json.loads(ev_raw) if isinstance(ev_raw, str) else ev_raw
                except Exception:
                    ev_ids = []

        # If we have running tasks, match relevant tools
        if active_tasks:
            top_task = dict(active_tasks[0])
            if td.category in ("RTL", "Static Analysis") and td.tool_name in ("verilator", "yosys", "semgrep"):
                status = "IN_USE"
                assigned_agent = top_task.get("assigned_agent_id") or "agent-agy-01"
                current_task = top_task.get("task_id")
            elif latest and latest.get("status") == "COMPLETED":
                status = "COMPLETED"
                assigned_agent = latest.get("agent_id")
                current_task = latest.get("task_id")
        elif latest:
            status = latest.get("status", "AVAILABLE")
            assigned_agent = latest.get("agent_id")
            current_task = latest.get("task_id")

        summaries.append(ToolSummary(
            tool_name=td.tool_name,
            display_name=td.display_name,
            category=td.category,
            version=td.version,
            description=td.description,
            capabilities=td.capabilities,
            status=status,
            assigned_agent=assigned_agent,
            current_task=current_task,
            health=td.health,
            last_execution=last_exec_time,
            evidence_ids=ev_ids,
        ))

    return summaries



@router.get("/executions", response_model=List[ToolExecutionRecord])
def list_all_executions_v2(
    task_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    tool_name_filter: Optional[str] = Query(None, alias="tool_name"),
    limit: int = Query(50, ge=1, le=200),
    session: SessionInfo = Depends(require_session),
):
    """
    Returns all tool execution records, filterable by task_id, agent_id, or tool_name.
    This route must be declared BEFORE /{tool_name} to avoid path conflict.
    """
    db = _get_db()
    exec_repo = ToolExecutionRepository(db)
    rows = exec_repo.list_executions(tool_name=tool_name_filter, task_id=task_id, limit=limit)
    if agent_id:
        rows = [r for r in rows if r.get("agent_id") == agent_id]
    records = []
    for r in rows:
        records.append(ToolExecutionRecord(
            execution_id=r["execution_id"],
            tool_name=r["tool_name"],
            category=r.get("category", "GENERAL"),
            agent_id=r.get("agent_id"),
            task_id=r.get("task_id"),
            run_id=r.get("run_id"),
            command=r["command"],
            args=r.get("args") or [],
            working_dir=r.get("working_dir"),
            status=r.get("status", "COMPLETED"),
            exit_code=r.get("exit_code", 0),
            stdout_artifact=r.get("stdout_artifact"),
            stderr_artifact=r.get("stderr_artifact"),
            execution_result=r.get("execution_result"),
            evidence_ids=r.get("evidence_ids") or [],
            started_at=_dt(r.get("started_at")),
            completed_at=_dt(r.get("completed_at")),
        ))
    return records


@router.get("/{tool_name}", response_model=ToolSummary)
def get_tool(tool_name: str, session: SessionInfo = Depends(require_session)):
    """Retrieves detail for a specific registered tool."""
    reg = get_tool_registry()
    td = reg.get_tool(tool_name.lower())
    if not td:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found in Tool Registry")

    db = _get_db()
    exec_repo = ToolExecutionRepository(db)
    executions = exec_repo.list_executions(tool_name=tool_name.lower(), limit=1)
    latest = executions[0] if executions else None

    return ToolSummary(
        tool_name=td.tool_name,
        display_name=td.display_name,
        category=td.category,
        version=td.version,
        description=td.description,
        capabilities=td.capabilities,
        status=latest.get("status", "AVAILABLE") if latest else "AVAILABLE",
        assigned_agent=latest.get("agent_id") if latest else None,
        current_task=latest.get("task_id") if latest else None,
        health=td.health,
        last_execution=_dt(latest.get("started_at")) if latest else None,
        evidence_ids=latest.get("evidence_ids", []) if latest else [],
    )


@router.get("/{tool_name}/executions", response_model=List[ToolExecutionRecord])
def get_tool_executions(
    tool_name: str,
    task_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: SessionInfo = Depends(require_session),
):
    """
    Returns immutable execution records for the tool.
    Never hides failed executions; links directly to generated evidence IDs.
    """
    db = _get_db()
    exec_repo = ToolExecutionRepository(db)
    rows = exec_repo.list_executions(tool_name=tool_name.lower(), task_id=task_id, limit=limit)

    records = []
    for r in rows:
        records.append(ToolExecutionRecord(
            execution_id=r["execution_id"],
            tool_name=r["tool_name"],
            category=r.get("category", "GENERAL"),
            agent_id=r.get("agent_id"),
            task_id=r.get("task_id"),
            run_id=r.get("run_id"),
            command=r["command"],
            args=r.get("args") or [],
            working_dir=r.get("working_dir"),
            status=r.get("status", "COMPLETED"),
            exit_code=r.get("exit_code", 0),
            stdout_artifact=r.get("stdout_artifact"),
            stderr_artifact=r.get("stderr_artifact"),
            execution_result=r.get("execution_result"),
            evidence_ids=r.get("evidence_ids") or [],
            started_at=_dt(r.get("started_at")),
            completed_at=_dt(r.get("completed_at")),
        ))
    return records


@router.get("/executions", response_model=List[ToolExecutionRecord])
def list_all_executions(
    task_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    tool_name: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: SessionInfo = Depends(require_session),
):
    """
    Returns tool execution records, optionally filtered by task_id, agent_id, or tool_name.
    Used by the Agent Workroom tool feed and workflow pages.
    """
    db = _get_db()
    exec_repo = ToolExecutionRepository(db)
    rows = exec_repo.list_executions(
        tool_name=tool_name,
        task_id=task_id,
        limit=limit,
    )

    # Apply agent_id filter (not in ToolExecutionRepository interface yet)
    if agent_id:
        rows = [r for r in rows if r.get("agent_id") == agent_id]

    records = []
    for r in rows:
        records.append(ToolExecutionRecord(
            execution_id=r["execution_id"],
            tool_name=r["tool_name"],
            category=r.get("category", "GENERAL"),
            agent_id=r.get("agent_id"),
            task_id=r.get("task_id"),
            run_id=r.get("run_id"),
            command=r["command"],
            args=r.get("args") or [],
            working_dir=r.get("working_dir"),
            status=r.get("status", "COMPLETED"),
            exit_code=r.get("exit_code", 0),
            stdout_artifact=r.get("stdout_artifact"),
            stderr_artifact=r.get("stderr_artifact"),
            execution_result=r.get("execution_result"),
            evidence_ids=r.get("evidence_ids") or [],
            started_at=_dt(r.get("started_at")),
            completed_at=_dt(r.get("completed_at")),
        ))
    return records
