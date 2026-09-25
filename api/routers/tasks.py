"""
LLMorch API — Tasks router.
GET /api/tasks              paginated list
GET /api/tasks/{task_id}    full detail with runs
"""

from __future__ import annotations

import json
import uuid
from typing import List, Optional
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from api.models import TaskSummary, TaskDetail, RunSummary, PaginatedResponse, TaskCreateRequest
from api.session import require_session, SessionInfo
from history import DatabaseService, TaskRepository, RunRepository
from history.database import get_db_path
from history.phase9_repositories import TargetRepositoryRepository
from api.realtime import event_manager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


def _task_to_summary(row: dict) -> TaskSummary:
    def _dt(v):
        if not v:
            return None
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v))
        except Exception:
            return None

    return TaskSummary(
        task_id=row["task_id"],
        workflow_id=row.get("workflow_id"),
        parent_task_id=row.get("parent_task_id"),
        objective=row.get("objective", ""),
        status=row.get("status", "UNKNOWN"),
        assigned_agent_id=row.get("assigned_agent_id"),
        retry_count=row.get("retry_count", 0) or 0,
        created_at=_dt(row.get("created_at")),
        started_at=_dt(row.get("started_at")),
        completed_at=_dt(row.get("completed_at")),
    )


def _run_to_summary(row: dict) -> RunSummary:
    def _dt(v):
        if not v:
            return None
        try:
            return datetime.fromisoformat(str(v))
        except Exception:
            return None

    return RunSummary(
        run_id=row["run_id"],
        task_id=row.get("task_id", ""),
        agent_id=row.get("agent_id", ""),
        status=row.get("status", "UNKNOWN"),
        start_time=_dt(row.get("start_time")),
        end_time=_dt(row.get("end_time")),
        exit_status=row.get("exit_status"),
        failure_reason=row.get("failure_reason"),
    )


@router.get("", response_model=PaginatedResponse)
def list_tasks(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    session: SessionInfo = Depends(require_session),
):
    db = _get_db()
    with db.get_connection() as conn:
        filters = []
        params: list = []
        if status:
            filters.append("status = ?")
            params.append(status)
        if agent_id:
            filters.append("assigned_agent_id = ?")
            params.append(agent_id)

        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        total = conn.execute(f"SELECT COUNT(*) FROM tasks {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM tasks {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    items = [_task_to_summary(dict(r)).model_dump() for r in rows]
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(task_id: str, session: SessionInfo = Depends(require_session)):
    db = _get_db()
    with db.get_connection() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        run_rows = conn.execute(
            "SELECT * FROM runs WHERE task_id = ? ORDER BY start_time ASC", (task_id,)
        ).fetchall()

    row_dict = dict(row)
    runs = [_run_to_summary(dict(r)) for r in run_rows]

    def _dt(v):
        if not v:
            return None
        try:
            return datetime.fromisoformat(str(v))
        except Exception:
            return None

    def _j(v):
        if not v:
            return []
        try:
            return json.loads(v) if isinstance(v, str) else v
        except Exception:
            return []

    return TaskDetail(
        task_id=row_dict["task_id"],
        workflow_id=row_dict.get("workflow_id"),
        parent_task_id=row_dict.get("parent_task_id"),
        objective=row_dict.get("objective", ""),
        status=row_dict.get("status", "UNKNOWN"),
        assigned_agent_id=row_dict.get("assigned_agent_id"),
        retry_count=row_dict.get("retry_count", 0) or 0,
        created_at=_dt(row_dict.get("created_at")),
        started_at=_dt(row_dict.get("started_at")),
        completed_at=_dt(row_dict.get("completed_at")),
        inputs=_j(row_dict.get("inputs")),
        dependencies=_j(row_dict.get("dependencies")),
        required_capabilities=_j(row_dict.get("required_capabilities")),
        preferred_roles=_j(row_dict.get("preferred_roles")),
        risk_level=row_dict.get("risk_level", "LOW"),
        runs=runs,
    )


@router.post("", response_model=TaskSummary)
async def create_task(
    request: TaskCreateRequest,
    session: SessionInfo = Depends(require_session),
):
    """
    Creates an investigation task bound to the authoritative Target / Attack Repository.
    """
    db = _get_db()
    target_repo = TargetRepositoryRepository(db)

    # 1. Authoritative repository determination
    repo_path = request.repository_path
    repo_name = None
    repo_family = "UNKNOWN"
    git_rev = None
    snap_id = None

    if not repo_path:
        cur = target_repo.get_current()
        if cur:
            repo_path = cur["repository_path"]
            repo_name = cur.get("repository_name", Path(repo_path).name)
            repo_family = cur.get("repository_family", "UNKNOWN")
            git_rev = cur.get("git_revision")
            snap_id = cur.get("snapshot_id")
        else:
            raise HTTPException(
                status_code=400,
                detail="A target repository must be selected before creating an investigation task",
            )
    else:
        p = Path(repo_path).resolve()
        repo_name = p.name
        cur = target_repo.get_current()
        if cur and cur["repository_path"] == str(p):
            repo_family = cur.get("repository_family", "UNKNOWN")
            git_rev = cur.get("git_revision")
            snap_id = cur.get("snapshot_id")

    # 2. Build task
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    workflow_id = request.workflow_id or f"wf-{uuid.uuid4().hex[:8]}"

    if isinstance(request.inputs, dict):
        inputs = dict(request.inputs)
    elif isinstance(request.inputs, list):
        inputs = {"items": request.inputs}
    else:
        inputs = {}
    inputs["repository_path"] = repo_path
    inputs["repository_name"] = repo_name
    inputs["repository_family"] = repo_family
    if git_rev:
        inputs["git_revision"] = git_rev
    if snap_id:
        inputs["snapshot_id"] = snap_id

    now = datetime.now(timezone.utc)
    task_data = {
        "task_id": task_id,
        "workflow_id": workflow_id,
        "parent_task_id": None,
        "objective": request.objective,
        "status": "QUEUED",
        "assigned_agent_id": request.assigned_agent_id,
        "retry_count": 0,
        "created_at": now.isoformat(),
        "started_at": None,
        "completed_at": None,
        "inputs": json.dumps(inputs),
        "dependencies": json.dumps([]),
        "required_capabilities": json.dumps(request.required_capabilities or []),
        "preferred_roles": json.dumps([]),
        "risk_level": request.risk_level or "LOW",
    }

    with db.get_connection() as conn:
        conn.execute("""
            INSERT INTO tasks (
                task_id, workflow_id, parent_task_id, objective, inputs, dependencies,
                required_capabilities, preferred_roles, risk_level, workspace_policy,
                tool_policy, budget, status, assigned_agent_id, retry_count,
                acceptance_criteria, result_ref, schema_version, created_at, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_data["task_id"],
            task_data["workflow_id"],
            task_data["parent_task_id"],
            task_data["objective"],
            task_data["inputs"],
            task_data["dependencies"],
            task_data["required_capabilities"],
            task_data["preferred_roles"],
            task_data["risk_level"],
            json.dumps({"workspace_class": "sandboxed"}),
            json.dumps({"allowed_tools": ["all"]}),
            json.dumps({"max_tokens": 100000}),
            task_data["status"],
            task_data["assigned_agent_id"],
            task_data["retry_count"],
            json.dumps(["objective_completed"]),
            None,
            "1.0",
            task_data["created_at"],
            task_data["started_at"],
            task_data["completed_at"],
        ))
        conn.commit()

    # WebSocket broadcast
    await event_manager.broadcast(
        event_type="TASK_CREATED",
        entity_type="task",
        entity_id=task_id,
        payload={
            "task_id": task_id,
            "workflow_id": workflow_id,
            "objective": request.objective,
            "assigned_agent_id": request.assigned_agent_id,
            "repository_path": repo_path,
        }
    )

    return TaskSummary(
        task_id=task_id,
        workflow_id=workflow_id,
        objective=request.objective,
        status="QUEUED",
        assigned_agent_id=request.assigned_agent_id,
        retry_count=0,
        created_at=now,
    )
