"""
Runtime Diagnostics Router (Phase 9 / Section 13 & 30).
Allows runtime comparison between OS process state and SQLite database state.
GET /api/debug/runs/{run_id}
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from history.database import get_db_path, DatabaseService
from api.session import require_session, SessionInfo

router = APIRouter(prefix="/api/debug", tags=["debug"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


def _is_pid_alive(pid: Optional[int]) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


@router.get("/runs/{run_id}")
def get_run_diagnostics(
    run_id: str,
    session: SessionInfo = Depends(require_session)
) -> Dict[str, Any]:
    """
    Returns exhaustive runtime diagnostics for run_id comparing OS process state,
    tool executions, tasks, attempts, and database state.
    """
    db = _get_db()
    with db.get_connection() as conn:
        run_row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if not run_row:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

        run = dict(run_row)
        plan_id = run.get("plan_id")
        project_id = run.get("project_id")

        # 1. Fetch tasks
        task_rows = conn.execute("""
            SELECT task_id, status, objective, role, assigned_agent_id,
                   parent_task_id, started_at, completed_at, heartbeat_at,
                   watchdog_status, failure_reason, dependencies
            FROM tasks
            WHERE plan_id = ? OR workflow_id = ?
            ORDER BY created_at ASC
        """, (plan_id, f"wf-{plan_id}")).fetchall()
        tasks = [dict(r) for r in task_rows]

        # 2. Fetch tool executions
        tool_rows = conn.execute("""
            SELECT execution_id, tool_name, status, exit_code, started_at, completed_at,
                   command, args, agent_id, task_id
            FROM tool_executions
            WHERE run_id = ?
            ORDER BY started_at DESC
        """, (run_id,)).fetchall()
        tool_execs = [dict(r) for r in tool_rows]

        # 3. Fetch task attempts
        attempt_rows = conn.execute("""
            SELECT attempt_id, task_id, attempt_number, status, agent_id,
                   role, created_at, completed_at
            FROM task_attempts
            WHERE run_id = ?
            ORDER BY attempt_number ASC
        """, (run_id,)).fetchall()
        attempts = [dict(r) for r in attempt_rows]

        # 4. Fetch last event
        last_event_row = conn.execute("""
            SELECT event_id, event_type, timestamp, actor, tool, payload
            FROM events
            WHERE run_id = ? OR project_id = ?
            ORDER BY timestamp DESC LIMIT 1
        """, (run_id, project_id)).fetchone()
        last_event = dict(last_event_row) if last_event_row else None
        if last_event and isinstance(last_event.get("payload"), str):
            try:
                last_event["payload"] = json.loads(last_event["payload"])
            except Exception:
                pass

        # 5. Process state & PIDs
        agent_pid = run.get("process_id")
        agent_alive = _is_pid_alive(agent_pid)

        latest_tool = tool_execs[0] if tool_execs else None
        tool_exit_code = latest_tool.get("exit_code") if latest_tool else None
        tool_pid = None  # Ephemeral short-lived CLI process

        # 6. Child task statistics (excluding root)
        root_task_id = f"task-root-{run_id}"
        leaf_tasks = [t for t in tasks if t["task_id"] != root_task_id]
        child_summary = {
            "total": len(leaf_tasks),
            "succeeded": sum(1 for t in leaf_tasks if t["status"] in ("SUCCEEDED", "COMPLETED")),
            "failed": sum(1 for t in leaf_tasks if t["status"] in ("FAILED", "TIMED_OUT", "CANCELLED")),
            "running": sum(1 for t in leaf_tasks if t["status"] == "RUNNING"),
            "queued": sum(1 for t in leaf_tasks if t["status"] == "QUEUED"),
            "blocked": sum(1 for t in leaf_tasks if t["status"] == "BLOCKED")
        }

        # 7. Pending dependencies
        pending_deps = []
        for t in leaf_tasks:
            if t["status"] == "BLOCKED":
                pending_deps.append({
                    "task_id": t["task_id"],
                    "dependencies": json.loads(t.get("dependencies") or "[]")
                })

        # 8. Heartbeat & transitions
        heartbeats = [t["heartbeat_at"] for t in tasks if t.get("heartbeat_at")]
        if run.get("last_heartbeat_at"):
            heartbeats.append(run["last_heartbeat_at"])
        last_heartbeat = max(heartbeats) if heartbeats else None

        return {
            "run_id": run_id,
            "project_id": project_id,
            "plan_id": plan_id,
            "run_state": {
                "status": run.get("status"),
                "run_state": run.get("run_state"),
                "start_time": run.get("start_time"),
                "end_time": run.get("end_time"),
                "completed_at": run.get("completed_at"),
                "active_duration_seconds": run.get("active_duration_seconds"),
                "repository_name": run.get("repository_name"),
            },
            "task_state": tasks,
            "attempt_state": attempts,
            "tool_executions": tool_execs,
            "agent_process_pid": agent_pid,
            "agent_process_alive": agent_alive,
            "tool_process_pid": tool_pid,
            "tool_process_alive": False,  # Tools execute via synchronous subprocess run
            "tool_exit_code": tool_exit_code,
            "last_event": last_event,
            "last_heartbeat": last_heartbeat,
            "child_tasks": child_summary,
            "pending_dependencies": pending_deps
        }


@router.get("/project/{project_id}")
def get_project_diagnostics(
    project_id: str,
    session: SessionInfo = Depends(require_session)
) -> Dict[str, Any]:
    """
    Returns developer diagnostics for a project (Section 45 & 46):
    Current project, current run, tasks, runtime state, process state,
    queue depth, heartbeat, dependencies, error count, and log file locations.
    """
    db = _get_db()
    with db.get_connection() as conn:
        proj = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        runs = conn.execute("SELECT * FROM runs WHERE project_id = ? ORDER BY start_time DESC LIMIT 5", (project_id,)).fetchall()
        tasks = conn.execute("SELECT * FROM tasks WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
        tools = conn.execute("SELECT * FROM tool_executions WHERE project_id = ? ORDER BY started_at DESC LIMIT 20", (project_id,)).fetchall()
        events = conn.execute("SELECT * FROM events WHERE project_id = ? ORDER BY timestamp DESC LIMIT 20", (project_id,)).fetchall()
        errors = conn.execute("SELECT COUNT(*) as count FROM events WHERE project_id = ? AND event_type LIKE '%ERROR%'", (project_id,)).fetchone()

    active_run = dict(runs[0]) if runs else None
    t_list = [dict(t) for t in tasks]
    pending_tasks = [t for t in t_list if t.get("status") in ("QUEUED", "PENDING", "ASSIGNED")]
    running_tasks = [t for t in t_list if t.get("status") == "RUNNING"]
    failed_tasks = [t for t in t_list if t.get("status") == "FAILED"]
    last_event = dict(events[0]) if events else None

    # Check project log file path
    log_dir = Path(f"logs/projects/{project_id}")
    project_log_path = str(log_dir.resolve()) if log_dir.exists() else f"logs/projects/{project_id}/project.log"
    run_log_path = f"logs/runs/{active_run.get('run_id')}/run.log" if active_run else "logs/runs/none/run.log"

    return {
        "status": "DIAGNOSTICS_READY",
        "current_project": dict(proj) if proj else {"project_id": project_id},
        "current_run": active_run,
        "current_task": dict(running_tasks[0]) if running_tasks else (dict(t_list[0]) if t_list else None),
        "runtime_state": active_run.get("status") if active_run else "READY",
        "websocket_state": "ACTIVE",
        "agent_process": {
            "name": "Antigravity CLI (AGY)",
            "executable": "/home/hackdac/.local/bin/agy",
            "active": len(running_tasks) > 0,
            "claude_invocations": 0
        },
        "tool_process": {
            "name": "Deterministic EDA & Source Tooling",
            "active": any(dict(t).get("status") == "RUNNING" for t in tools),
            "recent_count": len(tools)
        },
        "queue_depth": len(pending_tasks),
        "running_count": len(running_tasks),
        "failed_count": len(failed_tasks),
        "error_count": errors["count"] if errors else 0,
        "last_event": last_event,
        "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        "task_dependencies": [
            {"task_id": t["task_id"], "dependencies": json.loads(t.get("dependencies") or "[]")}
            for t in t_list if t.get("dependencies")
        ],
        "pending_work": len(pending_tasks),
        "log_locations": {
            "project_logs": project_log_path,
            "run_logs": run_log_path
        }
    }


@router.get("/logging/config")
def get_logging_configuration(session: SessionInfo = Depends(require_session)) -> Dict[str, Any]:
    """Retrieves log quota, directory locations, and retention status (Section 34, 35, 37)."""
    from history.log_retention import log_manager
    return log_manager.get_storage_stats()


@router.post("/logging/cleanup")
def trigger_log_cleanup(session: SessionInfo = Depends(require_session)) -> Dict[str, Any]:
    """Executes deterministic log cleanup prioritizing completed runs, old projects, and old app logs (Section 34, 35, 36)."""
    from history.log_retention import log_manager
    db = _get_db()
    with db.get_connection() as conn:
        res = log_manager.run_cleanup(db_conn=conn, force_under_quota=True)
    return res


@router.get("/logs/global")
def get_global_logs(
    component: Optional[str] = None,
    level: Optional[str] = None,
    project_id: Optional[str] = None,
    run_id: Optional[str] = None,
    task_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    session: SessionInfo = Depends(require_session)
) -> Dict[str, Any]:
    """Reads filtered global application logs (Section 32)."""
    from history.log_retention import log_manager
    return log_manager.read_filtered_logs(
        project_id=project_id,
        run_id=run_id,
        component=component,
        level=level,
        task_id=task_id,
        agent_id=agent_id,
        query=query,
        limit=limit,
        offset=offset
    )


@router.get("/logs/project/{project_id}")
def get_project_logs(
    project_id: str,
    run_id: Optional[str] = None,
    component: Optional[str] = None,
    level: Optional[str] = None,
    task_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    session: SessionInfo = Depends(require_session)
) -> Dict[str, Any]:
    """Reads filtered logs scoped strictly to the specified project (Section 33)."""
    from history.log_retention import log_manager
    return log_manager.read_filtered_logs(
        project_id=project_id,
        run_id=run_id,
        component=component,
        level=level,
        task_id=task_id,
        agent_id=agent_id,
        query=query,
        limit=limit,
        offset=offset
    )


@router.post("/reconcile")
def run_runtime_reconciliation(session: SessionInfo = Depends(require_session)) -> Dict[str, Any]:
    """Reconciles stuck attempts and tasks across the entire database (Section 43)."""
    db = _get_db()
    repaired_tasks = 0
    repaired_attempts = 0
    repaired_runs = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    with db.get_connection() as conn:
        # 1. Any task attempt RUNNING where parent task is terminal
        term_tasks = conn.execute("SELECT task_id, status FROM tasks WHERE status IN ('COMPLETED', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'STOPPED')").fetchall()
        for t in term_tasks:
            t_status = "COMPLETED" if t["status"] in ("COMPLETED", "SUCCEEDED") else "FAILED"
            res = conn.execute(
                "UPDATE task_attempts SET status = ?, completed_at = ? WHERE task_id = ? AND status IN ('RUNNING', 'PENDING')",
                (t_status, now_iso, t["task_id"])
            )
            repaired_attempts += res.rowcount

        # 2. Any runs where all tasks are terminal but run is left RUNNING
        runs = conn.execute("SELECT run_id, project_id FROM runs WHERE status = 'RUNNING'").fetchall()
        for r in runs:
            non_term = conn.execute("SELECT COUNT(*) FROM tasks WHERE project_id = ? AND status NOT IN ('COMPLETED', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'STOPPED')", (r["project_id"],)).fetchone()[0]
            if non_term == 0:
                conn.execute("UPDATE runs SET status = 'COMPLETED', end_time = ? WHERE run_id = ?", (now_iso, r["run_id"]))
                repaired_runs += 1

        conn.commit()

    return {
        "status": "RECONCILIATION_COMPLETED",
        "repaired_attempts": repaired_attempts,
        "repaired_runs": repaired_runs,
        "timestamp": now_iso
    }

