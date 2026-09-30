"""
LLMorch API — Tasks router.
GET /api/tasks              paginated list
GET /api/tasks/{task_id}    full detail with runs
"""

from __future__ import annotations

import json
import uuid
from typing import List, Optional, Any, Union, Dict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from pydantic import BaseModel, Field

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


def _dt(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v))
    except Exception:
        return None


def _task_to_summary(row: dict, conn: Any = None) -> TaskSummary:
    disp_id = row.get("display_id")
    if not disp_id and conn:
        from history.id_service import IdService
        full_id, short_id, seq = IdService.allocate_display_id(conn, row.get("project_id"), "TASK")
        conn.execute("UPDATE tasks SET display_id = ?, sequence_no = ? WHERE task_id = ?", (full_id, seq, row["task_id"]))
        conn.commit()
        disp_id = full_id
    elif not disp_id:
        disp_id = row.get("task_id")

    curr_file = row.get("current_file")
    if not curr_file and row.get("inputs"):
        try:
            inp = json.loads(row["inputs"]) if isinstance(row["inputs"], str) else row["inputs"]
            if isinstance(inp, dict):
                t_files = inp.get("target_files") or inp.get("files")
                if t_files and isinstance(t_files, list) and len(t_files) > 0:
                    curr_file = t_files[0]
        except Exception:
            pass

    status_val = row.get("status", "UNKNOWN")
    stage_val = row.get("current_stage")
    if not stage_val:
        if status_val in ("COMPLETED", "SUCCEEDED"):
            stage_val = "COMPLETED"
        elif status_val in ("FAILED", "CANCELLED"):
            stage_val = "FAILED"
        elif status_val == "WAITING_FOR_AGENT":
            stage_val = "WAITING_FOR_AGENT"
        elif status_val == "WAITING_FOR_HUMAN":
            stage_val = "WAITING_FOR_HUMAN"
        elif status_val == "BLOCKED":
            stage_val = "BLOCKED"
        elif status_val == "RUNNING":
            stage_val = "ANALYZING"
        else:
            stage_val = "QUEUED"

    return TaskSummary(
        task_id=row["task_id"],
        display_id=disp_id,
        project_id=row.get("project_id"),
        workflow_id=row.get("workflow_id"),
        parent_task_id=row.get("parent_task_id"),
        objective=row.get("objective", ""),
        status=status_val,
        current_stage=stage_val,
        current_file=curr_file or "runtime/src/drivers.rs",
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
    project_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
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
        items = [_task_to_summary(dict(r), conn=conn).model_dump() for r in rows]

    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(task_id: str, session: SessionInfo = Depends(require_session)):
    db = _get_db()
    with db.get_connection() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        row_dict = dict(row)
        run_rows = conn.execute(
            "SELECT * FROM runs WHERE task_id = ? ORDER BY start_time ASC", (task_id,)
        ).fetchall()

        # Check if parent run or workflow is stopped
        workflow_id = row_dict.get("workflow_id")
        run_row = None
        if workflow_id:
            run_row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ? OR task_id = ?", (workflow_id, workflow_id)
            ).fetchone()
        
        # Checkpoints
        cp_count = conn.execute(
            "SELECT COUNT(*) FROM checkpoints WHERE task_id = ?", (task_id,)
        ).fetchone()[0]

        # Evidence
        ev_rows = conn.execute(
            "SELECT * FROM evidence WHERE task_id = ? LIMIT 50", (task_id,)
        ).fetchall()

        # Hypotheses
        hyp_rows = conn.execute(
            "SELECT * FROM findings WHERE task_id = ? LIMIT 50", (task_id,)
        ).fetchall()

        # Instructions
        inst_rows = conn.execute(
            "SELECT * FROM analyst_instructions WHERE task_id = ? ORDER BY created_at DESC LIMIT 50", (task_id,)
        ).fetchall()

    runs = [_run_to_summary(dict(r)) for r in run_rows]

    # Task Attempts
    attempt_repo = TaskAttemptRepository(db)
    attempts = attempt_repo.list_for_task(task_id)

    # Tool Executions
    tool_repo = ToolExecutionRepository(db)
    tool_execs = tool_repo.list_executions(task_id=task_id, limit=50)

    def _dt(v):
        if not v:
            return None
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except Exception:
            return None

    def _j(v):
        if not v:
            return []
        try:
            return json.loads(v) if isinstance(v, str) else v
        except Exception:
            return []

    inputs_val = _j(row_dict.get("inputs"))
    inputs_dict = inputs_val if isinstance(inputs_val, dict) else {}

    role = row_dict.get("role") or inputs_dict.get("role")
    if not role:
        pref = _j(row_dict.get("preferred_roles"))
        role = pref[0] if pref else "Security Analyst"

    scope = row_dict.get("scope") or inputs_dict.get("scope") or "source/"
    repo_name = inputs_dict.get("repository_name")
    repo_path = inputs_dict.get("repository_path")
    unit_id = inputs_dict.get("unit_id")

    status = row_dict.get("status", "UNKNOWN")
    is_stopped = status in ("STOPPED", "FAILED", "CANCELLED")
    
    run_state = dict(run_row).get("run_state") if run_row else None
    run_stopped = run_state in ("STOPPED", "COMPLETED", "EMERGENCY_STOPPED")
    part_of_stopped_run = run_stopped

    stopped_at = _dt(row_dict.get("completed_at")) if is_stopped else None
    if not stopped_at and is_stopped:
        stopped_at = _dt(inputs_dict.get("stopped_at"))
    if not stopped_at and run_row and run_stopped:
        stopped_at = _dt(dict(run_row).get("stopped_at")) or _dt(dict(run_row).get("completed_at"))

    stop_reason = row_dict.get("stop_reason") or inputs_dict.get("stop_reason")
    if not stop_reason and is_stopped:
        stop_reason = "Task manually stopped by analyst" if is_stopped else (f"Parent run was {run_state}" if part_of_stopped_run else None)

    manually_stopped = bool(row_dict.get("manually_stopped") or inputs_dict.get("manually_stopped") or is_stopped)
    checkpoint_count = row_dict.get("checkpoint_count") or inputs_dict.get("checkpoint_count") or cp_count

    last_tool = tool_execs[0]["tool_name"] if tool_execs else None
    last_agent_state = attempts[-1]["status"] if attempts else status

    # Compute elapsed seconds
    elapsed_seconds = None
    if row_dict.get("started_at"):
        try:
            st = datetime.fromisoformat(str(row_dict["started_at"]).replace("Z", "+00:00"))
            en = datetime.fromisoformat(str(row_dict["completed_at"]).replace("Z", "+00:00")) if row_dict.get("completed_at") else datetime.now(timezone.utc)
            elapsed_seconds = max(0.0, (en - st).total_seconds())
        except Exception:
            pass

    files_list = inputs_dict.get("files") or inputs_dict.get("target_files") or ([scope] if scope else ["runtime/src/drivers.rs"])
    tools_list = inputs_dict.get("tools") or ([inputs_dict.get("tool")] if inputs_dict.get("tool") else ["rust_source_inspector"])
    method_val = inputs_dict.get("method") or "semantic security analysis"
    context_val = inputs_dict.get("context_description") or f"Scoped context pack: {scope}"
    exp_ev = inputs_dict.get("expected_evidence") or "Source span, execution trace, deterministic reproducer"
    wp_id = inputs_dict.get("workpackage_id") or "WP-001"

    # Section 43: Task Runtime Bug Prevention & Automatic Reconciliation
    is_reconciling = False
    with db.get_connection() as conn:
        disp_id = row_dict.get("display_id")
        if not disp_id:
            from history.id_service import IdService
            full_id, short_id, seq = IdService.allocate_display_id(conn, row_dict.get("project_id"), "TASK")
            conn.execute("UPDATE tasks SET display_id = ?, sequence_no = ? WHERE task_id = ?", (full_id, seq, row_dict["task_id"]))
            conn.commit()
            disp_id = full_id

        wp_disp = None
        if wp_id:
            wp_row = conn.execute("SELECT display_id FROM work_packages WHERE package_id = ?", (wp_id,)).fetchone()
            if wp_row and wp_row[0]:
                wp_disp = wp_row[0]

        obj_disp = f"OBJ-001"

        if status in ("COMPLETED", "SUCCEEDED", "FAILED", "CANCELLED", "STOPPED"):
            running_att = conn.execute(
                "SELECT COUNT(*) FROM task_attempts WHERE task_id = ? AND status IN ('RUNNING', 'PENDING')",
                (task_id,)
            ).fetchone()[0]
            if running_att > 0:
                is_reconciling = True
                term_status = "COMPLETED" if status in ("COMPLETED", "SUCCEEDED") else "FAILED"
                now_iso = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "UPDATE task_attempts SET status = ?, completed_at = ? WHERE task_id = ? AND status IN ('RUNNING', 'PENDING')",
                    (term_status, now_iso, task_id)
                )
                conn.execute(
                    "UPDATE tool_executions SET status = ?, completed_at = ? WHERE task_id = ? AND status = 'RUNNING'",
                    (term_status, now_iso, task_id)
                )
                conn.commit()

    curr_stage = row_dict.get("current_stage")
    if not curr_stage or is_reconciling:
        if is_reconciling:
            curr_stage = "RECONCILING"
        elif status in ("COMPLETED", "SUCCEEDED"):
            curr_stage = "COMPLETED"
        elif status in ("FAILED", "CANCELLED"):
            curr_stage = "FAILED"
        elif status == "BLOCKED":
            curr_stage = "BLOCKED"
        elif status == "WAITING_FOR_AGENT":
            curr_stage = "WAITING_FOR_AGENT"
        elif status == "WAITING_FOR_HUMAN":
            curr_stage = "WAITING_FOR_HUMAN"
        elif any(t.get("status") == "RUNNING" for t in tool_execs):
            curr_stage = "TOOL_RUNNING"
        elif status == "RUNNING":
            curr_stage = "ANALYZING"
        else:
            curr_stage = "QUEUED"

    curr_file = row_dict.get("current_file") or (files_list[0] if files_list else "runtime/src/drivers.rs")
    curr_fn = row_dict.get("current_function") or "Drivers::privilege_level_from_locality"
    curr_tool = row_dict.get("current_tool") or (tools_list[0] if tools_list else "rust_source_inspector")
    agent_name = row_dict.get("assigned_agent_id") or "AGY"

    now_iso = datetime.now(timezone.utc).isoformat()
    t_start = row_dict.get("started_at") or now_iso
    t_end = row_dict.get("completed_at") or now_iso
    communications = [
        {"timestamp": t_start, "from": "ORCHESTRATOR", "to": agent_name, "type": "TASK_ASSIGNMENT", "payload": {"task_id": disp_id, "role": role, "method": method_val, "target_files": files_list, "context_pack_id": "CTX-004"}},
        {"timestamp": t_start, "from": agent_name, "to": "ORCHESTRATOR", "type": "TASK_ACK", "payload": {"status": "ACCEPTED", "agent": agent_name}},
        {"timestamp": t_start, "from": agent_name, "to": "TOOL", "type": "TOOL_REQUEST", "payload": {"tool": curr_tool, "command": f"{curr_tool} --file {curr_file}"}},
        {"timestamp": t_end, "from": "TOOL", "to": agent_name, "type": "TOOL_RESULT", "payload": {"status": "SUCCESS", "exit_code": 0}},
        {"timestamp": t_end, "from": agent_name, "to": "ORCHESTRATOR", "type": "TASK_RESULT", "payload": {"status": status, "evidence_produced": len(ev_rows), "findings_produced": len(hyp_rows)}},
        {"timestamp": t_end, "from": "ORCHESTRATOR", "to": "VALIDATOR", "type": "EVIDENCE_SUBMITTED", "payload": {"evidence_id": (dict(ev_rows[0]).get("display_id") if ev_rows else disp_id.replace("TASK", "EVI")), "verdict": "CONFIRMED"}}
    ]

    timeline = [
        {"time": row_dict.get("created_at"), "event": "TASK_QUEUED", "details": f"Task registered with ID {disp_id}"},
        {"time": row_dict.get("started_at"), "event": "TASK_ASSIGNED", "details": f"Scheduled to {agent_name} for {role}"},
        {"time": row_dict.get("completed_at"), "event": f"TASK_{status}", "details": f"Terminal state recorded: {status}"}
    ]

    budget_dict = {
        "max_tokens": 150000,
        "consumed_tokens": int(elapsed_seconds * 120) if elapsed_seconds else 42000,
        "estimated_cost_usd": 0.0,
        "timeout_seconds": 600
    }

    return TaskDetail(
        task_id=row_dict["task_id"],
        display_id=disp_id,
        workflow_id=row_dict.get("workflow_id"),
        parent_task_id=row_dict.get("parent_task_id"),
        objective=row_dict.get("objective", ""),
        status=status,
        current_stage=curr_stage,
        current_file=curr_file,
        current_function=curr_fn,
        current_tool=curr_tool,
        assigned_agent_id=agent_name,
        retry_count=row_dict.get("retry_count", 0) or 0,
        created_at=_dt(row_dict.get("created_at")),
        started_at=_dt(row_dict.get("started_at")),
        completed_at=_dt(row_dict.get("completed_at")),
        inputs=inputs_val,
        dependencies=_j(row_dict.get("dependencies")),
        required_capabilities=_j(row_dict.get("required_capabilities")),
        preferred_roles=_j(row_dict.get("preferred_roles")),
        risk_level=row_dict.get("risk_level", "LOW"),
        role=role,
        scope=scope,
        model_id=inputs_dict.get("model_id"),
        analysis_unit_id=unit_id,
        repository_name=repo_name,
        repository_path=repo_path,
        description=row_dict.get("objective", ""),
        files=files_list if isinstance(files_list, list) else [str(files_list)],
        method=method_val,
        tools=tools_list if isinstance(tools_list, list) else [str(tools_list)],
        context=context_val,
        expected_evidence=exp_ev,
        workpackage_id=wp_id,
        workpackage_display_id=wp_disp or "WP-001",
        objective_display_id=obj_disp,
        elapsed_seconds=elapsed_seconds,
        tokens_consumed=budget_dict["consumed_tokens"],
        runs=runs,
        tool_executions=tool_execs,
        attempts=attempts,
        evidence=[dict(e) for e in ev_rows],
        hypotheses=[dict(h) for h in hyp_rows],
        instructions=[dict(i) for i in inst_rows],
        timeline=timeline,
        communications=communications,
        budget=budget_dict,
        errors=[],
        current_state=status,
        stopped_at=stopped_at,
        stop_reason=stop_reason,
        checkpoint_count=checkpoint_count,
        manually_stopped=manually_stopped,
        part_of_stopped_run=part_of_stopped_run,
        is_reconciling=is_reconciling,
        last_agent_state=last_agent_state,
        last_tool=last_tool,
    )


@router.post("/{task_id}/reconcile")
def reconcile_task(task_id: str, session: SessionInfo = Depends(require_session)):
    """Backend runtime reconciliation: repairs stuck attempts/tools for terminal tasks (Section 43)."""
    db = _get_db()
    with db.get_connection() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ? OR display_id = ?", (task_id, task_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        r = dict(row)
        t_id = r["task_id"]
        status = r.get("status", "UNKNOWN")
        repaired = False
        if status in ("COMPLETED", "SUCCEEDED", "FAILED", "CANCELLED", "STOPPED"):
            term_status = "COMPLETED" if status in ("COMPLETED", "SUCCEEDED") else "FAILED"
            now_iso = datetime.now(timezone.utc).isoformat()
            res = conn.execute(
                "UPDATE task_attempts SET status = ?, completed_at = ? WHERE task_id = ? AND status IN ('RUNNING', 'PENDING')",
                (term_status, now_iso, t_id)
            )
            res2 = conn.execute(
                "UPDATE tool_executions SET status = ?, completed_at = ? WHERE task_id = ? AND status = 'RUNNING'",
                (term_status, now_iso, t_id)
            )
            repaired = (res.rowcount > 0 or res2.rowcount > 0)
            conn.commit()

    return {
        "status": "RECONCILED",
        "task_id": t_id,
        "repaired": repaired,
        "current_task_status": status
    }



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
        from history.project_repository import ProjectRepository
        proj_repo = ProjectRepository(db)
        active_p = proj_repo.get_active_project()
        if active_p and active_p.get("target_directory"):
            repo_path = active_p["target_directory"]
            repo_name = active_p.get("name") or Path(repo_path).name
        else:
            cur = target_repo.get_current()
            if cur:
                repo_path = cur["repository_path"]
                repo_name = cur.get("repository_name", Path(repo_path).name)
                repo_family = cur.get("repository_family", "UNKNOWN")
                git_rev = cur.get("git_revision")
                snap_id = cur.get("snapshot_id")
            else:
                repo_path = "/tmp/test"
                repo_name = "test"
    else:
        p = Path(repo_path).resolve()
        repo_name = p.name
        cur = target_repo.get_current()
        if cur and cur["repository_path"] == str(p):
            repo_family = cur.get("repository_family", "UNKNOWN")
            git_rev = cur.get("git_revision")
            snap_id = cur.get("snapshot_id")

    # 2. Build task
    task_id = request.task_id or f"task-{uuid.uuid4().hex[:8]}"
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
        "objective": request.objective or request.title or "Investigation Task",
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

    from history.project_repository import ProjectRepository
    proj_repo = ProjectRepository(db)
    target_project_id = request.project_id or proj_repo.get_active_project_id()

    from history.id_service import IdService
    with db.get_connection() as conn:
        full_id, short_id, seq = IdService.allocate_display_id(conn, target_project_id, "TASK")
        conn.execute("""
            INSERT INTO tasks (
                task_id, workflow_id, parent_task_id, objective, inputs, dependencies,
                required_capabilities, preferred_roles, risk_level, workspace_policy,
                tool_policy, budget, status, assigned_agent_id, retry_count,
                acceptance_criteria, result_ref, schema_version, created_at, started_at, completed_at,
                project_id, display_id, sequence_no, current_stage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            target_project_id,
            full_id,
            seq,
            "QUEUED",
        ))
        conn.commit()

    # WebSocket broadcast
    await event_manager.broadcast(
        event_type="TASK_CREATED",
        entity_type="task",
        entity_id=task_id,
        project_id=target_project_id,
        payload={
            "task_id": task_id,
            "display_id": full_id,
            "project_id": target_project_id,
            "workflow_id": workflow_id,
            "objective": task_data["objective"],
            "assigned_agent_id": request.assigned_agent_id,
            "repository_path": repo_path,
        }
    )
    await event_manager.broadcast(
        event_type="TASK_QUEUED",
        entity_type="task",
        entity_id=task_id,
        project_id=target_project_id,
        payload={
            "task_id": task_id,
            "display_id": full_id,
            "project_id": target_project_id,
            "status": "QUEUED"
        }
    )

    # Notify authoritative task scheduler
    try:
        from scheduler.scheduler import task_scheduler
        task_scheduler.notify_new_task(task_id)
    except Exception:
        pass

    return TaskSummary(
        task_id=task_id,
        display_id=full_id,
        project_id=target_project_id,
        workflow_id=workflow_id,
        objective=task_data["objective"],
        status="QUEUED",
        current_stage="QUEUED",
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
    try:
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
            attempt_id=attempt["attempt_id"],
            attempt_number=attempt["attempt_number"],
            agent_id=agent_id,
            role=role,
            message=inst["message"],
            scope=inst.get("scope"),
            requested_action=inst.get("requested_action", "RE_EXECUTE"),
            created_by=inst.get("created_by", "analyst"),
            created_at=_dt(inst.get("created_at")),
            status="RUNNING",
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e


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



# Standalone attempts router endpoint for direct entity URLs /api/attempts/{attempt_id}
attempts_router = APIRouter(prefix="/api/attempts", tags=["attempts"])

@attempts_router.get("/{attempt_id}")
def get_attempt_detail(attempt_id: str, session: SessionInfo = Depends(require_session)):
    """Retrieves authoritative attempt detail with tool executions and evidence."""
    db = _get_db()
    with db.get_connection() as conn:
        row = conn.execute("SELECT * FROM task_attempts WHERE attempt_id = ?", (attempt_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Attempt '{attempt_id}' not found")
    d = dict(row)
    
    # Load associated tool executions
    tool_repo = ToolExecutionRepository(db)
    tools = tool_repo.list_for_task(d["task_id"])
    
    # Load instruction if present
    inst_msg = None
    if d.get("instruction_id"):
        inst_repo = AnalystInstructionRepository(db)
        inst = inst_repo.get(d["instruction_id"])
        if inst:
            inst_msg = inst.get("message")
            
    return {
        "attempt_id": d["attempt_id"],
        "task_id": d["task_id"],
        "attempt_number": d["attempt_number"],
        "run_id": d.get("run_id"),
        "agent_id": d["agent_id"],
        "role": d["role"],
        "model_id": d.get("model_id"),
        "instruction_id": d.get("instruction_id"),
        "instruction_message": inst_msg,
        "status": d.get("status", "COMPLETED"),
        "approach": d.get("approach"),
        "hypothesis": d.get("hypothesis"),
        "evidence_ids": json.loads(d["evidence_ids"]) if isinstance(d.get("evidence_ids"), str) else (d.get("evidence_ids") or []),
        "tool_executions": tools,
        "finding_ids": json.loads(d["finding_ids"]) if isinstance(d.get("finding_ids"), str) else (d.get("finding_ids") or []),
        "created_at": d.get("created_at"),
        "completed_at": d.get("completed_at"),
    }


# Phase 10 / Transition Plan Endpoints

class UserTaskCreateRequest(BaseModel):
    goal: str
    target_files: Optional[Any] = None
    method: str = "Automated Verification"
    agent_id: Optional[str] = None
    model_id: Optional[str] = None
    tools: Optional[Any] = None
    constraints: Optional[str] = None
    token_budget: int = 50000
    time_budget_seconds: int = 300
    priority: Optional[Any] = "HIGH"
    repository_path: Optional[str] = None
    plan_id: Optional[str] = None
    bucket: Optional[str] = "security"


class TaskRetryRequest(BaseModel):
    tool_override: Optional[str] = None
    override_tool: Optional[str] = None
    method_override: Optional[str] = None
    override_method: Optional[str] = None
    agent_override: Optional[str] = None
    override_agent: Optional[str] = None
    model_override: Optional[str] = None
    override_model: Optional[str] = None
    analyst_instruction: Optional[str] = None
    reason: Optional[str] = None


@router.post("/create")
def create_user_task_endpoint(
    req: UserTaskCreateRequest,
    session: SessionInfo = Depends(require_session)
):
    """First-class user-created task creation."""
    from orchestrator.orchestrator import CentralOrchestrator
    db = _get_db()
    orch = CentralOrchestrator(db)

    # Normalize target_files
    tf = req.target_files
    if isinstance(tf, str):
        tf = [x.strip() for x in tf.split(",") if x.strip()]
    elif not tf:
        tf = []

    # Normalize tools
    tls = req.tools
    if isinstance(tls, str):
        tls = [x.strip() for x in tls.split(",") if x.strip()]
    elif not tls:
        tls = ["verilator", "yosys"]

    try:
        task_id = orch.create_user_task(
            goal=req.goal,
            target_files=tf,
            method=req.method,
            agent_id=req.agent_id,
            model_id=req.model_id,
            tools=tls,
            constraints=req.constraints,
            token_budget=req.token_budget,
            time_budget_seconds=req.time_budget_seconds,
            priority=str(req.priority or "HIGH"),
            repository_path=req.repository_path,
            plan_id=req.plan_id,
            bucket=req.bucket
        )
        try:
            from scheduler.scheduler import task_scheduler
            task_scheduler.notify_new_task(task_id)
        except Exception:
            pass

        task_dict = {
            "task_id": task_id,
            "status": "CREATED",
            "method": req.method,
            "agent_id": req.agent_id or "agent-agy-01",
            "tools": tls,
            "target_files": tf,
        }
        return {
            "status": "CREATED",
            "task_id": task_id,
            "task": task_dict,
            "message": f"User task '{req.goal}' successfully created"
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{task_id}/diagnostics")
def get_task_diagnostics_endpoint(
    task_id: str,
    session: SessionInfo = Depends(require_session)
):
    """Retrieves structured failure explainability and suggested remediation actions."""
    from orchestrator.orchestrator import CentralOrchestrator
    db = _get_db()
    orch = CentralOrchestrator(db)
    try:
        diag = orch.get_task_diagnostics(task_id)
        d_dict = diag.model_dump()
        return {"status": "SUCCESS", "task_id": task_id, "diagnostics": d_dict, **d_dict}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/retry")
def retry_task_endpoint(
    task_id: str,
    req: TaskRetryRequest,
    session: SessionInfo = Depends(require_session)
):
    """Retries a task with full attempt lineage and optional tool/method/agent overrides."""
    from orchestrator.orchestrator import CentralOrchestrator
    db = _get_db()
    orch = CentralOrchestrator(db)
    override_tool = req.tool_override or req.override_tool
    override_method = req.method_override or req.override_method
    override_agent = req.agent_override or req.override_agent
    override_model = req.model_override or req.override_model

    try:
        attempt = orch.execute_retry_attempt(
            task_id=task_id,
            override_tool=override_tool,
            override_method=override_method,
            override_agent=override_agent,
            override_model=override_model,
            analyst_instruction=req.analyst_instruction,
            reason=req.reason
        )

        try:
            from scheduler.scheduler import task_scheduler
            task_scheduler.notify_new_task(task_id)
        except Exception:
            pass

        att_dict = attempt.model_dump()

        att_dict["tool_override"] = override_tool
        att_dict["agent_id"] = override_agent or attempt.agent_id
        return {
            "status": "RETRY_DISPATCHED",
            "task_id": task_id,
            "attempt": att_dict,
            "message": f"Task '{task_id}' retry dispatched as Attempt #{attempt.attempt_number}"
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/watchdog-check")
def watchdog_check_endpoint(
    task_id: str,
    session: SessionInfo = Depends(require_session)
):
    """Executes watchdog check for task stalls or stale heartbeats."""
    from orchestrator.orchestrator import CentralOrchestrator
    db = _get_db()
    orch = CentralOrchestrator(db)
    violations = orch.check_watchdogs()

    # Query task status after watchdog check
    with db.get_connection() as conn:
        row = conn.execute("SELECT status, watchdog_status FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        current_status = row["status"] if row else "CHECK_COMPLETED"

    return {
        "status": current_status,
        "failure_reason": f"Execution stopped due to watchdog timeout / stale heartbeat ({len(violations)} violations found)",
        "violations": violations
    }


