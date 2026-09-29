"""
Runtime Diagnostics Router (Phase 9 / Section 13 & 30).
Allows runtime comparison between OS process state and SQLite database state.
GET /api/debug/runs/{run_id}
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
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
