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

from api.models import (
    TaskSummary, TaskDetail, RunSummary, PaginatedResponse, TaskCreateRequest,
    AnalystInstructionRequest, AnalystInstructionItem, TaskAttemptSummary, TaskReRunRequest
)
from api.session import require_session, SessionInfo
from history import (
    DatabaseService, TaskRepository, RunRepository,
    AnalystInstructionRepository, TaskAttemptRepository, ToolExecutionRepository
)
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


@router.post("/{task_id}/instructions", response_model=AnalystInstructionItem)
async def add_task_instruction(
    task_id: str,
    request: AnalystInstructionRequest,
    session: SessionInfo = Depends(require_session),
):
    """
    Submits an analyst instruction for a task.
    Creates an immutable AnalystInstruction record, spawns a new TaskAttempt (Attempt 2+),
    preserves previous attempt lineage, and broadcasts AGENT_INSTRUCTION_ADDED and TASK_ATTEMPT_STARTED.
    """
    db = _get_db()
    with db.get_connection() as conn:
        task_row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if not task_row:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    t_dict = dict(task_row)
    agent_id = request.agent_id or t_dict.get("assigned_agent_id") or "agent-agy-01"
    role = request.role or t_dict.get("role") or "RTL Security Analyst"

    inst_repo = AnalystInstructionRepository(db)
    attempt_repo = TaskAttemptRepository(db)

    # 1. Save immutable instruction
    inst = inst_repo.save({
        "task_id": task_id,
        "run_id": t_dict.get("workflow_id"),
        "agent_id": agent_id,
        "role": role,
        "message": request.message,
        "scope": request.scope or t_dict.get("scope"),
        "requested_action": request.requested_action or "RE_EXECUTE",
        "created_by": session.role or "analyst",
    })

    # 2. Spawn new TaskAttempt preserving previous attempt
    existing_attempts = attempt_repo.list_for_task(task_id)
    parent_attempt = existing_attempts[-1] if existing_attempts else None
    parent_attempt_id = parent_attempt["attempt_id"] if parent_attempt else None

    attempt = attempt_repo.create_attempt(
        task_id=task_id,
        agent_id=agent_id,
        role=role,
        instruction_id=inst["instruction_id"],
        parent_attempt_id=parent_attempt_id,
        run_id=t_dict.get("workflow_id"),
        approach=f"Re-execution based on analyst instruction: {request.message[:80]}",
    )

    # 3. Broadcast events
    await event_manager.broadcast(
        event_type="AGENT_INSTRUCTION_ADDED",
        entity_type="task",
        entity_id=task_id,
        payload={
            "instruction_id": inst["instruction_id"],
            "task_id": task_id,
            "agent_id": agent_id,
            "message": request.message,
            "attempt_number": attempt["attempt_number"],
        }
    )

    await event_manager.broadcast(
        event_type="TASK_ATTEMPT_STARTED",
        entity_type="task",
        entity_id=task_id,
        payload={
            "attempt_id": attempt["attempt_id"],
            "task_id": task_id,
            "attempt_number": attempt["attempt_number"],
            "agent_id": agent_id,
            "role": role,
            "instruction_id": inst["instruction_id"],
        }
    )

    return AnalystInstructionItem(
        instruction_id=inst["instruction_id"],
        run_id=inst.get("run_id"),
        task_id=task_id,
        attempt_id=attempt["attempt_number"],
        agent_id=agent_id,
        role=role,
        message=inst["message"],
        scope=inst.get("scope"),
        requested_action=inst.get("requested_action", "RE_EXECUTE"),
        created_by=inst.get("created_by", "analyst"),
        created_at=_dt(inst.get("created_at")),
    )


@router.get("/{task_id}/attempts", response_model=List[TaskAttemptSummary])
def list_task_attempts(task_id: str, session: SessionInfo = Depends(require_session)):
    """Returns chronological attempt lineage for a task (Attempt 1, Attempt 2, etc.)."""
    db = _get_db()
    attempt_repo = TaskAttemptRepository(db)
    attempts = attempt_repo.list_for_task(task_id)

    # If no attempts recorded yet but task exists, seed initial Attempt 1
    if not attempts:
        with db.get_connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row:
            r = dict(row)
            att = attempt_repo.create_attempt(
                task_id=task_id,
                agent_id=r.get("assigned_agent_id") or "agent-agy-01",
                role=r.get("role") or "general_analysis",
                approach="Initial exploration and hypothesis generation",
            )
            attempts = [att]

    items = []
    for a in attempts:
        items.append(TaskAttemptSummary(
            attempt_id=a["attempt_id"],
            task_id=a["task_id"],
            attempt_number=a["attempt_number"],
            run_id=a.get("run_id"),
            parent_run_id=a.get("parent_run_id"),
            parent_attempt_id=a.get("parent_attempt_id"),
            agent_id=a["agent_id"],
            model_id=a.get("model_id"),
            role=a.get("role", "general_analysis"),
            instruction_id=a.get("instruction_id"),
            status=a.get("status", "COMPLETED"),
            approach=a.get("approach"),
            hypothesis=a.get("hypothesis"),
            evidence_ids=a.get("evidence_ids") or [],
            tool_execution_ids=a.get("tool_execution_ids") or [],
            finding_ids=a.get("finding_ids") or [],
            created_at=_dt(a.get("created_at")),
            completed_at=_dt(a.get("completed_at")),
        ))
    return items


@router.get("/{task_id}/instructions", response_model=List[AnalystInstructionItem])
def list_task_instructions(task_id: str, session: SessionInfo = Depends(require_session)):
    """Returns all analyst instructions submitted for the given task."""
    db = _get_db()
    inst_repo = AnalystInstructionRepository(db)
    items = inst_repo.list_for_task(task_id)
    return [
        AnalystInstructionItem(
            instruction_id=i["instruction_id"],
            run_id=i.get("run_id"),
            task_id=i["task_id"],
            attempt_id=i.get("attempt_id", 1),
            agent_id=i.get("agent_id"),
            role=i.get("role"),
            message=i["message"],
            scope=i.get("scope"),
            requested_action=i.get("requested_action", "RE_EXECUTE"),
            created_by=i.get("created_by", "analyst"),
            created_at=_dt(i.get("created_at")),
        )
        for i in items
    ]


@router.post("/{task_id}/re-run", response_model=TaskAttemptSummary)
async def rerun_task_with_options(
    task_id: str,
    request: TaskReRunRequest,
    session: SessionInfo = Depends(require_session),
):
    """
    Reruns a task creating a new attempt while preserving previous attempts and lineage.
    Allows configuring instruction, scope, agent, role, and model.
    """
    db = _get_db()
    with db.get_connection() as conn:
        task_row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if not task_row:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    t_dict = dict(task_row)
    agent_id = request.agent_id or t_dict.get("assigned_agent_id") or "agent-agy-01"
    role = request.role or t_dict.get("role") or "general_analysis"
    model_id = request.model_id or t_dict.get("model_id")

    inst_id = None
    if request.instruction:
        inst_repo = AnalystInstructionRepository(db)
        inst = inst_repo.save({
            "task_id": task_id,
            "run_id": t_dict.get("workflow_id"),
            "agent_id": agent_id,
            "role": role,
            "message": request.instruction,
            "scope": request.scope,
            "requested_action": "RE_EXECUTE",
            "created_by": session.role or "analyst",
        })
        inst_id = inst["instruction_id"]

    attempt_repo = TaskAttemptRepository(db)
    existing_attempts = attempt_repo.list_for_task(task_id)
    parent_attempt = existing_attempts[-1] if existing_attempts else None
    parent_attempt_id = parent_attempt["attempt_id"] if parent_attempt else None

    attempt = attempt_repo.create_attempt(
        task_id=task_id,
        agent_id=agent_id,
        model_id=model_id,
        role=role,
        instruction_id=inst_id,
        parent_attempt_id=parent_attempt_id,
        run_id=t_dict.get("workflow_id"),
        approach=f"Re-run with options: {request.instruction or 'Analyst re-run'}",
    )

    await event_manager.broadcast(
        event_type="TASK_ATTEMPT_STARTED",
        entity_type="task",
        entity_id=task_id,
        payload={
            "attempt_id": attempt["attempt_id"],
            "task_id": task_id,
            "attempt_number": attempt["attempt_number"],
            "agent_id": agent_id,
            "role": role,
            "instruction_id": inst_id,
        }
    )

    return TaskAttemptSummary(
        attempt_id=attempt["attempt_id"],
        task_id=task_id,
        attempt_number=attempt["attempt_number"],
        run_id=attempt.get("run_id"),
        parent_run_id=attempt.get("parent_run_id"),
        parent_attempt_id=parent_attempt_id,
        agent_id=agent_id,
        model_id=model_id,
        role=role,
        instruction_id=inst_id,
        status="RUNNING",
        approach=attempt.get("approach"),
        created_at=_dt(attempt.get("created_at")),
    )

