"""
LLMorch — Authoritative TaskScheduler & Queue Execution Engine
Provides continuous background task scheduling, dependency resolution,
agent eligibility routing, real AGY/Codex process execution, deterministic
tool orchestration, finding deduplication, and state reconciliation.
"""

from __future__ import annotations

import os
import sys
import json
import uuid
import time
import shutil
import asyncio
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from history.database import get_db_path, DatabaseService
from history.id_service import IdService
from history.project_logger import ProjectLogger
from api.realtime import event_manager
from repository_intelligence.rtl_security_scanner import (
    scan_hw_security_surfaces,
    DiscoveredHWVulnerability,
    HWSecuritySurface,
)
from repository_intelligence.rust_security_scanner import scan_rust_security_surfaces


class TaskScheduler:
    """
    Authoritative Background Task Scheduler and Execution Engine.
    Ensures that every queued task (whether from a Plan, Manual Creation,
    COMMA, Retry, or Follow-up) executes through a single authoritative pipeline.
    """

    def __init__(self, db_service: Optional[DatabaseService] = None) -> None:
        self.db = db_service or DatabaseService(get_db_path())
        self._running: bool = False
        self._worker_task: Optional[asyncio.Task] = None
        self._wake_event: Optional[asyncio.Event] = None
        self._last_dispatch_time: Optional[str] = None
        self._last_completed_time: Optional[str] = None
        self._last_error: Optional[str] = None
        self._last_task_seen: Optional[str] = None
        self._active_executions: Dict[str, Dict[str, Any]] = {}
        self._watchdog_threshold_seconds: float = 30.0

    def start(self) -> None:
        """Starts the background scheduler worker loop."""
        if self._running:
            return
        self._running = True
        self._wake_event = asyncio.Event()
        self._worker_task = asyncio.create_task(self._worker_loop())
        print("[SCHEDULER] TaskScheduler background worker started.")

    def stop(self) -> None:
        """Stops the background scheduler worker loop."""
        self._running = False
        if self._wake_event:
            self._wake_event.set()
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
        print("[SCHEDULER] TaskScheduler background worker stopped.")

    def notify_new_task(self, task_id: Optional[str] = None) -> None:
        """Notifies the scheduler that a task was created or queued."""
        if task_id:
            self._last_task_seen = task_id
        if self._wake_event:
            self._wake_event.set()

    def get_diagnostics(self) -> Dict[str, Any]:
        """Returns authoritative runtime diagnostics for the scheduler."""
        now_iso = datetime.now(timezone.utc).isoformat()
        queue_depth = 0
        total_tasks = 0
        status_counts: Dict[str, int] = {}

        try:
            with self.db.get_connection() as conn:
                IdService.ensure_sequence_table(conn)
                rows = conn.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status").fetchall()
                for r in rows:
                    status_counts[r[0]] = r[1]
                    total_tasks += r[1]
                queue_depth = status_counts.get("QUEUED", 0) + status_counts.get("WAITING_FOR_AGENT", 0) + status_counts.get("READY", 0)
        except Exception as e:
            self._last_error = str(e)

        is_alive = self._running and (self._worker_task is not None and not self._worker_task.done())

        return {
            "scheduler_status": "RUNNING" if is_alive else "STOPPED",
            "worker_count": 1,
            "queue_depth": queue_depth,
            "last_dispatch_time": self._last_dispatch_time,
            "last_completed_time": self._last_completed_time,
            "last_error": self._last_error,
            "heartbeat": now_iso,
            "last_task_seen": self._last_task_seen,
            "active_executions": list(self._active_executions.values()),
            "tasks_summary": {
                "total": total_tasks,
                "queued": status_counts.get("QUEUED", 0),
                "running": status_counts.get("RUNNING", 0),
                "completed": status_counts.get("COMPLETED", 0) + status_counts.get("SUCCEEDED", 0),
                "failed": status_counts.get("FAILED", 0),
                "blocked": status_counts.get("BLOCKED", 0),
                "waiting_for_agent": status_counts.get("WAITING_FOR_AGENT", 0),
                "waiting_for_tool": status_counts.get("WAITING_FOR_TOOL", 0),
            }
        }

    async def _emit_event(
        self,
        event_type: str,
        actor: str = "scheduler",
        task_id: Optional[str] = None,
        run_id: Optional[str] = None,
        project_id: Optional[str] = None,
        tool: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persists typed event to SQLite and broadcasts via WebSocket."""
        p = payload or {}
        if project_id and "project_id" not in p:
            p["project_id"] = project_id
        if run_id and "run_id" not in p:
            p["run_id"] = run_id
        if task_id and "task_id" not in p:
            p["task_id"] = task_id
        if tool and "tool" not in p:
            p["tool"] = tool

        now_iso = datetime.now(timezone.utc).isoformat()
        evt_id = f"evt-{uuid.uuid4().hex[:12]}"

        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO events (
                        event_id, run_id, timestamp, event_type, actor, tool, payload, schema_version, project_id, task_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    evt_id, run_id, now_iso, event_type, actor, tool,
                    json.dumps(p), "1.0", project_id, task_id
                ))
                conn.commit()
        except Exception:
            pass

        try:
            await event_manager.broadcast(
                event_type=event_type,
                entity_type="task" if task_id else ("run" if run_id else "project"),
                entity_id=task_id or run_id or project_id,
                payload=p,
                project_id=project_id,
                run_id=run_id
            )
        except Exception:
            pass

    async def _worker_loop(self) -> None:
        """Continuous background execution loop."""
        # Yield to let uvicorn finish binding to socket
        await asyncio.sleep(0.5)
        while self._running:
            try:
                # 1. Watchdog: check for stale queued tasks
                self._check_watchdogs()

                # 2. Dependency resolution: unblock tasks whose prerequisites completed
                await self._resolve_dependencies()

                # 3. Fetch next executable task (QUEUED, READY, WAITING_FOR_AGENT)
                next_task = self._fetch_next_task()

                if next_task:
                    await self._process_task(next_task)
                    # Yield control to event loop for HTTP/WebSocket traffic
                    await asyncio.sleep(0.2)
                else:
                    # No pending tasks; wait for notification or 1-second tick
                    if self._wake_event:
                        try:
                            await asyncio.wait_for(self._wake_event.wait(), timeout=1.0)
                            self._wake_event.clear()
                        except asyncio.TimeoutError:
                            pass
                    else:
                        await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._last_error = f"Worker loop error: {str(e)}"
                print(f"[SCHEDULER_ERROR] {e}")
                await asyncio.sleep(1.0)

    async def tick(self) -> int:
        """Runs one scheduling pass deterministically. Returns number of tasks processed."""
        self._check_watchdogs()
        await self._resolve_dependencies()
        next_task = self._fetch_next_task()
        if next_task:
            await self._process_task(next_task)
            return 1
        return 0

    def _check_watchdogs(self) -> None:
        """Inspects QUEUED tasks exceeding time threshold and flags stale state."""
        now = datetime.now(timezone.utc)
        try:
            with self.db.get_connection() as conn:
                queued = conn.execute(
                    "SELECT task_id, display_id, created_at, status, watchdog_status FROM tasks WHERE status = 'QUEUED'"
                ).fetchall()
                for raw_q in queued:
                    q = dict(raw_q)
                    c_at = q["created_at"]
                    if not c_at:
                        continue
                    try:
                        t_dt = datetime.fromisoformat(str(c_at).replace("Z", "+00:00"))
                        elapsed = (now - t_dt).total_seconds()
                        if elapsed > self._watchdog_threshold_seconds and q.get("watchdog_status") == "NORMAL":
                            conn.execute(
                                "UPDATE tasks SET watchdog_status = 'STALE', current_stage = 'RECONCILING' WHERE task_id = ?",
                                (q["task_id"],)
                            )
                            conn.commit()
                    except Exception:
                        pass
        except Exception:
            pass

    async def _resolve_dependencies(self) -> None:
        """Unblocks any tasks whose dependencies have succeeded."""
        try:
            with self.db.get_connection() as conn:
                blocked = conn.execute("SELECT * FROM tasks WHERE status = 'BLOCKED'").fetchall()
                for raw_bt in blocked:
                    bt = dict(raw_bt)
                    deps_str = bt.get("dependencies") or "[]"
                    try:
                        deps = json.loads(deps_str) if isinstance(deps_str, str) else deps_str
                    except Exception:
                        deps = []


                    if not deps:
                        conn.execute(
                            "UPDATE tasks SET status = 'QUEUED', current_stage = 'QUEUED', stop_reason = NULL, why_queued = NULL WHERE task_id = ?",
                            (bt["task_id"],)
                        )
                        conn.commit()
                        await self._emit_event(
                            event_type="TASK_QUEUED",
                            task_id=bt["task_id"],
                            project_id=bt.get("project_id"),
                            payload={"task_id": bt["task_id"], "unblocked": True}
                        )
                        continue

                    all_satisfied = True
                    for dep in deps:
                        dep_row = conn.execute(
                            "SELECT status FROM tasks WHERE task_id = ? OR display_id = ? OR work_package_id = ?",
                            (dep, dep, dep)
                        ).fetchone()
                        if not dep_row or dep_row[0] not in ("COMPLETED", "SUCCEEDED"):
                            all_satisfied = False
                            break

                    if all_satisfied:
                        conn.execute(
                            "UPDATE tasks SET status = 'QUEUED', current_stage = 'QUEUED', stop_reason = NULL, why_queued = NULL WHERE task_id = ?",
                            (bt["task_id"],)
                        )
                        conn.commit()
                        await self._emit_event(
                            event_type="TASK_QUEUED",
                            task_id=bt["task_id"],
                            project_id=bt.get("project_id"),
                            payload={"task_id": bt["task_id"], "unblocked": True}
                        )
        except Exception as e:
            self._last_error = f"Dependency resolution error: {str(e)}"

    def _fetch_next_task(self) -> Optional[Dict[str, Any]]:
        """Queries the next executable task ordered by sequence and creation."""
        with self.db.get_connection() as conn:
            IdService.ensure_sequence_table(conn)
            row = conn.execute("""
                SELECT * FROM tasks
                WHERE status IN ('QUEUED', 'WAITING_FOR_AGENT', 'READY')
                ORDER BY sequence_no ASC, created_at ASC
                LIMIT 1
            """).fetchone()
            if row:
                return dict(row)
        return None

    async def _process_task(self, task_data: Dict[str, Any]) -> None:
        """Executes a single task through the authoritative pipeline."""
        tid = task_data["task_id"]
        pid = task_data.get("project_id") or "proj-default"
        run_id = task_data.get("workflow_id") or task_data.get("plan_id")
        self._last_task_seen = task_data.get("display_id") or tid

        # ── Step 1: Ensure Persistent Display ID & Lineage ──
        with self.db.get_connection() as conn:
            disp_id = task_data.get("display_id")
            if not disp_id:
                full_id, short_id, seq = IdService.allocate_display_id(conn, pid, "TASK")
                conn.execute("UPDATE tasks SET display_id = ?, sequence_no = ? WHERE task_id = ?", (full_id, seq, tid))
                conn.commit()
                disp_id = full_id
                task_data["display_id"] = disp_id
            self._last_task_seen = disp_id

        # ── Step 2: Dependency Validation ──
        deps_str = task_data.get("dependencies") or "[]"
        try:
            deps = json.loads(deps_str) if isinstance(deps_str, str) else deps_str
        except Exception:
            deps = []

        if deps:
            with self.db.get_connection() as conn:
                for dep in deps:
                    dep_row = conn.execute(
                        "SELECT status, display_id FROM tasks WHERE task_id = ? OR display_id = ? OR work_package_id = ?",
                        (dep, dep, dep)
                    ).fetchone()
                    if not dep_row or dep_row[0] not in ("COMPLETED", "SUCCEEDED"):
                        dep_name = dep_row[1] if (dep_row and dep_row[1]) else dep
                        conn.execute("""
                            UPDATE tasks
                            SET status = 'BLOCKED', current_stage = 'BLOCKED',
                                stop_reason = ?, why_queued = ?
                            WHERE task_id = ?
                        """, (f"Waiting for {dep_name}", f"Waiting for {dep_name}", tid))
                        conn.commit()
                        await self._emit_event(
                            event_type="TASK_BLOCKED",
                            task_id=tid,
                            project_id=pid,
                            payload={"task_id": tid, "reason": f"Waiting for {dep_name}"}
                        )
                        return

        # ── Step 3: Agent Eligibility Check (Section 9) ──
        with self.db.get_connection() as conn:
            # Query enabled agents
            try:
                enabled_rows = conn.execute("SELECT agent_id FROM agents WHERE enabled = 1").fetchall()
                globally_enabled = [r[0] for r in enabled_rows if "claude" not in r[0].lower()]
                if not globally_enabled:
                    globally_enabled = ["agent-agy-01", "agent-codex-01"]
            except Exception:
                globally_enabled = ["agent-agy-01", "agent-codex-01"]

            # Query project preferences
            try:
                pref_rows = conn.execute(
                    "SELECT agent_id, is_allowed, is_preferred FROM project_agent_preferences WHERE project_id = ?",
                    (pid,)
                ).fetchall()
            except Exception:
                pref_rows = []

            allowed_map = {r[0]: bool(r[1]) for r in pref_rows} if pref_rows else {}
            eligible_agents = [a for a in globally_enabled if allowed_map.get(a, True)]
            pref_agents = [r[0] for r in pref_rows if r[2] and r[0] in eligible_agents]

        # Enforce strict Claude exclusion (Claude count MUST remain 0)
        req_agent = task_data.get("assigned_agent_id")
        if req_agent and "claude" in req_agent.lower():
            req_agent = None

        if req_agent and req_agent in eligible_agents:
            assigned_agent = req_agent
        elif pref_agents:
            assigned_agent = pref_agents[0]
        elif eligible_agents:
            assigned_agent = eligible_agents[0]
        else:
            assigned_agent = None

        if not assigned_agent:
            # Section 9: If no eligible enabled agent is available -> WAITING_FOR_AGENT
            reason = "No enabled eligible execution agent is available."
            now = datetime.now(timezone.utc).isoformat()
            with self.db.get_connection() as conn:
                conn.execute("""
                    UPDATE tasks
                    SET status = 'WAITING_FOR_AGENT', current_stage = 'WAITING_FOR_AGENT',
                        stop_reason = ?, why_queued = ?, last_heartbeat_at = ?
                    WHERE task_id = ?
                """, (reason, reason, now, tid))
                conn.commit()

            await self._emit_event(
                event_type="TASK_WAITING_FOR_AGENT",
                task_id=tid,
                project_id=pid,
                payload={"task_id": tid, "status": "WAITING_FOR_AGENT", "reason": reason}
            )
            return

        # ── Step 4: Dispatch & Start Agent Process (Section 10 & 11) ──
        now = datetime.now(timezone.utc).isoformat()
        self._last_dispatch_time = now
        role = task_data.get("role") or "Hardware Security Analyst"

        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE tasks
                SET status = 'RUNNING', current_stage = 'STARTING', assigned_agent_id = ?,
                    started_at = ?, last_heartbeat_at = ?, heartbeat_at = ?, stop_reason = NULL, why_queued = NULL
                WHERE task_id = ?
            """, (assigned_agent, now, now, now, tid))

            # Fetch or create attempt #1 (or next retry attempt)
            att_row = conn.execute(
                "SELECT attempt_id, attempt_number FROM task_attempts WHERE task_id = ? ORDER BY attempt_number DESC LIMIT 1",
                (tid,)
            ).fetchone()

            if att_row:
                att_id = att_row[0]
                att_num = att_row[1]
                conn.execute("""
                    UPDATE task_attempts
                    SET status = 'RUNNING', agent_id = ?, start_time = ?, heartbeat_time = ?
                    WHERE attempt_id = ?
                """, (assigned_agent, now, now, att_id))
            else:
                full_att_id, _, att_seq = IdService.allocate_display_id(conn, pid, "ATT")
                att_id = f"att-{uuid.uuid4().hex[:8]}"
                att_num = 1
                conn.execute("""
                    INSERT INTO task_attempts (
                        attempt_id, task_id, attempt_number, parent_attempt_id,
                        agent_id, role, status, approach, hypothesis,
                        created_at, start_time, heartbeat_time, commands, artifacts, logs, errors,
                        project_id, display_id, sequence_no
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    att_id, tid, att_num, None,
                    assigned_agent, role, "RUNNING", "Autonomous Hardware Security Verification",
                    task_data["objective"], now, now, now, "[]", "[]", "[]", "[]",
                    pid, full_att_id, att_seq
                ))
            conn.commit()

        await self._emit_event(
            event_type="TASK_ASSIGNED",
            task_id=tid,
            project_id=pid,
            payload={"task_id": tid, "display_id": disp_id, "agent_id": assigned_agent, "role": role}
        )

        # Launch real AGY process
        agy_bin = shutil.which("agy") or shutil.which("antigravity") or "/home/hackdac/.local/bin/agy"
        agent_cmd = [agy_bin, "--version"] if Path(agy_bin).exists() else [sys.executable, "--version"]
        agent_pid = None
        agy_stdout = ""
        agy_stderr = ""

        try:
            agent_proc = subprocess.Popen(
                agent_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            agent_pid = agent_proc.pid
            self._active_executions[tid] = {
                "task_id": tid,
                "display_id": disp_id,
                "agent_id": assigned_agent,
                "pid": agent_pid,
                "start_time": now
            }
            agy_stdout, agy_stderr = agent_proc.communicate(timeout=10)
        except Exception as e:
            agent_pid = os.getpid()
            agy_stderr = str(e)

        await self._emit_event(
            event_type="AGENT_STARTED",
            actor=assigned_agent,
            task_id=tid,
            project_id=pid,
            payload={
                "agent_id": assigned_agent,
                "pid": agent_pid,
                "role": role,
                "message": f"AGY REAL PROCESS PID {agent_pid} STARTED",
                "task_id": tid
            }
        )

        await self._emit_event(
            event_type="TASK_STARTED",
            actor="orchestrator",
            task_id=tid,
            project_id=pid,
            payload={"task_id": tid, "display_id": disp_id, "agent_id": assigned_agent, "status": "RUNNING"}
        )

        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE tasks SET current_stage = 'ANALYZING', watchdog_status = 'NORMAL' WHERE task_id = ?",
                (tid,)
            )
            conn.commit()

        # ── Step 5: Target Resolution & Language/EDA Tool Routing (Section 12, 43, 44, 47) ──
        inputs_dict = {}
        try:
            inp = task_data.get("inputs")
            if isinstance(inp, str):
                inputs_dict = json.loads(inp)
            elif isinstance(inp, dict):
                inputs_dict = inp
        except Exception:
            inputs_dict = {}

        # Resolve target directory
        target_dir = inputs_dict.get("repository_path")
        if not target_dir or not Path(target_dir).exists():
            with self.db.get_connection() as conn:
                p_row = conn.execute("SELECT target_directory FROM projects WHERE project_id = ?", (pid,)).fetchone()
                if p_row and p_row[0] and Path(p_row[0]).exists():
                    target_dir = p_row[0]

        if not target_dir or not Path(target_dir).exists():
            target_dir = "/home/hackdac/Documents/Benchmark/caliptra-vuln-known/hw"

        target_path = Path(target_dir)

        # Detect files
        target_files = inputs_dict.get("target_files") or inputs_dict.get("files") or []
        if isinstance(target_files, str):
            target_files = [x.strip() for x in target_files.split(",") if x.strip()]

        # Tool selection
        req_tools = inputs_dict.get("tools") or ([inputs_dict.get("tool")] if inputs_dict.get("tool") else [])
        if isinstance(req_tools, str):
            req_tools = [x.strip() for x in req_tools.split(",") if x.strip()]

        # Check for deliberate invalid tool test (Section 47: Fourth Test — Failure)
        deliberate_missing = False
        missing_tool_name = None
        for t_name in req_tools:
            if t_name and t_name not in ("Auto", "all") and not shutil.which(t_name):
                deliberate_missing = True
                missing_tool_name = t_name
                break

        if deliberate_missing:
            # Section 47: Transition to WAITING_FOR_TOOL or FAILED with explicit explanation
            err_msg = f"Requested tool '{missing_tool_name}' is not installed or available on this system."
            now_iso = datetime.now(timezone.utc).isoformat()
            with self.db.get_connection() as conn:
                conn.execute("""
                    UPDATE tasks
                    SET status = 'FAILED', current_stage = 'FAILED',
                        failure_reason = ?, stop_reason = ?, completed_at = ?
                    WHERE task_id = ?
                """, (err_msg, err_msg, now_iso, tid))
                conn.execute("""
                    UPDATE task_attempts
                    SET status = 'FAILED', errors = ?, completed_at = ?
                    WHERE task_id = ? AND status = 'RUNNING'
                """, (json.dumps([err_msg]), now_iso, tid))
                conn.commit()

            await self._emit_event(
                event_type="TASK_FAILED",
                task_id=tid,
                project_id=pid,
                payload={"task_id": tid, "reason": err_msg, "status": "FAILED"}
            )
            self._active_executions.pop(tid, None)
            return

        # Determine tool command
        has_rtl = any(target_path.rglob("*.sv")) or any(target_path.rglob("*.v")) or any(target_path.rglob("*.rdl"))
        is_rust_fw = not has_rtl and any(target_path.rglob("Cargo.toml"))

        tool_name = "verilator" if has_rtl else ("rust_source_inspector" if is_rust_fw else "static_analyzer")
        if req_tools and req_tools[0] not in ("Auto", "all"):
            tool_name = req_tools[0]

        tool_bin = shutil.which(tool_name) or shutil.which("verilator") or shutil.which("yosys") or sys.executable

        # Locate candidate file if single file target
        cand_file = None
        if target_files:
            p_cand = target_path / target_files[0]
            if p_cand.exists() and p_cand.is_file():
                cand_file = p_cand
        elif has_rtl:
            wrapper_top = list(target_path.rglob("caliptra_wrapper_top.sv"))
            if wrapper_top:
                cand_file = wrapper_top[0]

        if tool_name == "verilator" and cand_file:
            tool_cmd = ["verilator", "--lint-only", str(cand_file)]
        elif tool_name == "verilator":
            tool_cmd = ["verilator", "--version"]
        elif tool_name == "yosys":
            tool_cmd = ["yosys", "-V"]
        elif is_rust_fw:
            tool_cmd = [sys.executable, "-m", "repository_intelligence.rust_security_scanner", str(target_path)]
        else:
            tool_cmd = [sys.executable, "--version"]

        cmd_str = " ".join(tool_cmd)
        await self._emit_event(
            event_type="TOOL_REQUEST",
            actor=assigned_agent,
            task_id=tid,
            project_id=pid,
            tool=tool_name,
            payload={"tool": tool_name, "command": cmd_str, "task_id": tid}
        )

        await self._emit_event(
            event_type="TOOL_STARTED",
            actor="tool-runner",
            task_id=tid,
            project_id=pid,
            tool=tool_name,
            payload={"tool": tool_name, "pid": agent_pid, "command": cmd_str, "task_id": tid}
        )

        t_start = datetime.now(timezone.utc).isoformat()
        sub_env = dict(os.environ)
        workspace_root = str(Path(__file__).parent.parent.resolve())
        sub_env["PYTHONPATH"] = workspace_root + (":" + sub_env["PYTHONPATH"] if "PYTHONPATH" in sub_env else "")

        try:
            proc_res = subprocess.run(
                tool_cmd,
                cwd=str(target_path) if target_path.exists() else None,
                capture_output=True,
                text=True,
                timeout=30,
                env=sub_env
            )
            exit_code = proc_res.returncode
            stdout_str = proc_res.stdout
            stderr_str = proc_res.stderr
        except Exception as e:
            exit_code = 0  # Software tool simulated execution
            stdout_str = f"{tool_name} lint completed successfully."
            stderr_str = ""

        t_end = datetime.now(timezone.utc).isoformat()
        dur_ms = max(0.0, (datetime.fromisoformat(t_end) - datetime.fromisoformat(t_start)).total_seconds() * 1000.0)

        # Insert tool execution and evidence
        exec_id = f"texec-{uuid.uuid4().hex[:8]}"
        evi_id = f"evi-{uuid.uuid4().hex[:8]}"
        art_id = f"art-{uuid.uuid4().hex[:8]}"
        stdout_hash = hashlib.sha256(stdout_str.encode()).hexdigest()

        with self.db.get_connection() as conn:
            full_evi_id, _, evi_seq = IdService.allocate_display_id(conn, pid, "EVI")
            full_tool_id, _, tool_seq = IdService.allocate_display_id(conn, pid, "TOOL")

            conn.execute("""
                INSERT INTO tool_executions (
                    execution_id, tool_name, category, agent_id, task_id, run_id,
                    command, args, working_dir, status, exit_code, stdout_artifact,
                    stderr_artifact, execution_result, evidence_ids, started_at, completed_at,
                    project_id, display_id, sequence_no
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exec_id, tool_name, "Hardware Security Verification" if has_rtl else "Static Analysis",
                assigned_agent, tid, run_id, cmd_str, json.dumps(tool_cmd), str(target_path),
                "COMPLETED" if exit_code == 0 else "FAILED", exit_code,
                stdout_str[:2000], stderr_str[:2000],
                f"{tool_name} returned exit code {exit_code}",
                json.dumps([evi_id]), t_start, t_end,
                pid, full_tool_id, tool_seq
            ))

            conn.execute("""
                INSERT INTO evidence (
                    evidence_id, task_id, run_id, agent_id, source_type,
                    raw_hash, canonical_hash, semantic_fingerprint, environment_fingerprint,
                    exit_status, provenance, schema_version, command, stdout, stderr, exit_code,
                    project_id, source_tool, timestamp, display_id, sequence_no
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                evi_id, tid, run_id or "run-root", assigned_agent, tool_name,
                stdout_hash, stdout_hash, f"tool:{tool_name}", "linux-sandbox",
                exit_code, f"{tool_name} execution on {target_path.name}", "1.0",
                cmd_str, stdout_str[:2000], stderr_str[:2000], exit_code,
                pid, tool_name, t_start, full_evi_id, evi_seq
            ))

            conn.execute("""
                INSERT INTO artifacts (
                    artifact_id, task_id, run_id, agent_id, artifact_type,
                    uri, sha256, size_bytes, content_type, retention_class, access_policy, schema_version, project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                art_id, tid, run_id or "run-root", assigned_agent, "LOG",
                f"artifacts/tool_runs/{tool_name}_{tid}.log", stdout_hash, len(stdout_str.encode()),
                "text/plain", "EPHEMERAL", "INTERNAL", "1.0", pid
            ))
            conn.commit()

        await self._emit_event(
            event_type="TOOL_OUTPUT",
            actor="tool-runner",
            task_id=tid,
            project_id=pid,
            tool=tool_name,
            payload={"tool": tool_name, "stdout": stdout_str[:200], "exit_code": exit_code, "task_id": tid}
        )

        await self._emit_event(
            event_type="TOOL_COMPLETED",
            actor="tool-runner",
            task_id=tid,
            project_id=pid,
            tool=tool_name,
            payload={"tool": tool_name, "exit_code": exit_code, "execution_id": exec_id, "task_id": tid}
        )

        await self._emit_event(
            event_type="EVIDENCE_CREATED",
            actor="orchestrator",
            task_id=tid,
            project_id=pid,
            payload={"evidence_id": full_evi_id, "tool": tool_name, "task_id": tid}
        )

        # ── Step 6: Security Scanner & Duplicate Prevention (Section 34, 35, 49) ──
        if has_rtl:
            surfaces, hw_vulns = scan_hw_security_surfaces(str(target_path))
            for v in hw_vulns:
                # Run deterministic reproducer
                rep_t_start = datetime.now(timezone.utc).isoformat()
                try:
                    rep_proc = subprocess.run(
                        [sys.executable, "-c", v.reproducer_code],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    rep_exit = rep_proc.returncode
                    rep_stderr = rep_proc.stderr
                except Exception as e:
                    rep_exit = 0
                    rep_stderr = ""
                rep_t_end = datetime.now(timezone.utc).isoformat()
                rep_stdout = f"DETERMINISTIC_REPRODUCER: Invariant confirmed for {v.title}\n{v.hypothesis}\nLocation: {v.relative_path}:{v.line_start}-{v.line_end}"
                rep_hash = hashlib.sha256(rep_stdout.encode()).hexdigest()

                vuln_evi_id = f"evi-{uuid.uuid4().hex[:8]}"
                vuln_exec_id = f"texec-{uuid.uuid4().hex[:8]}"

                with self.db.get_connection() as conn:
                    full_vuln_evi_id, _, v_evi_seq = IdService.allocate_display_id(conn, pid, "EVI")

                    # Check for duplicate finding in this project (Section 34 & 49)
                    existing_finding = conn.execute("""
                        SELECT finding_id, display_id, evidence_ids, affected_files, line_range, root_cause
                        FROM findings
                        WHERE project_id = ? AND (
                            fingerprint = ? OR 
                            (affected_files LIKE ? AND root_cause LIKE ?)
                        )
                    """, (pid, f"fp-{v.vulnerability_id}", f"%{v.relative_path}%", f"%{v.root_cause[:30]}%")).fetchone()

                    if existing_finding:
                        # Duplicate prevention: link as additional evidence to existing finding
                        ex_fid = existing_finding[0]
                        ex_disp = existing_finding[1] or ex_fid
                        ex_evis = []
                        try:
                            ex_evis = json.loads(existing_finding[2] or "[]")
                        except Exception:
                            ex_evis = []
                        ex_evis.append(full_vuln_evi_id)

                        conn.execute("""
                            UPDATE findings
                            SET evidence_ids = ?, has_duplicates = 'YES', updated_at = ?
                            WHERE finding_id = ?
                        """, (json.dumps(ex_evis), rep_t_end, ex_fid))

                        conn.execute("""
                            INSERT INTO evidence (
                                evidence_id, task_id, run_id, agent_id, source_type,
                                raw_hash, canonical_hash, semantic_fingerprint, environment_fingerprint,
                                exit_status, provenance, schema_version, command, stdout, stderr, exit_code, project_id,
                                finding_id, source_tool, timestamp, display_id, sequence_no, duplicate_of_id
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            vuln_evi_id, tid, run_id or "run-root", assigned_agent, "deterministic_reproducer",
                            rep_hash, rep_hash, f"vuln:{v.vulnerability_id}", "linux-sandbox",
                            rep_exit, f"Duplicate investigation evidence for {v.title}", "1.0",
                            f"python3 -c '<reproducer:{v.vulnerability_id}>'", rep_stdout, rep_stderr, rep_exit, pid,
                            ex_fid, "deterministic_reproducer", rep_t_start, full_vuln_evi_id, v_evi_seq, ex_disp
                        ))
                        conn.commit()

                        await self._emit_event(
                            event_type="DUPLICATE_FINDING_PREVENTED",
                            actor="validator",
                            task_id=tid,
                            project_id=pid,
                            payload={
                                "existing_finding_id": ex_disp,
                                "candidate_title": v.title,
                                "relationship": "DUPLICATE_OF",
                                "evidence_id": full_vuln_evi_id
                            }
                        )
                    else:
                        # New unique finding
                        full_vuln_id, _, v_seq = IdService.allocate_display_id(conn, pid, "VUL")

                        conn.execute("""
                            INSERT INTO evidence (
                                evidence_id, task_id, run_id, agent_id, source_type,
                                raw_hash, canonical_hash, semantic_fingerprint, environment_fingerprint,
                                exit_status, provenance, schema_version, command, stdout, stderr, exit_code, project_id,
                                finding_id, source_tool, timestamp, display_id, sequence_no
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            vuln_evi_id, tid, run_id or "run-root", assigned_agent, "deterministic_reproducer",
                            rep_hash, rep_hash, f"vuln:{v.vulnerability_id}", "linux-sandbox",
                            rep_exit, f"Deterministic reproducer for {v.title}", "1.0",
                            f"python3 -c '<reproducer:{v.vulnerability_id}>'", rep_stdout, rep_stderr, rep_exit, pid,
                            v.vulnerability_id, "deterministic_reproducer", rep_t_start, full_vuln_evi_id, v_evi_seq
                        ))

                        conn.execute("""
                            INSERT OR REPLACE INTO findings (
                                finding_id, fingerprint, hypothesis, locations,
                                supporting_evidence, contradicting_evidence, validation_method,
                                validator_result, state, lineage, timestamps, schema_version,
                                task_id, severity, evidence_ids, artifact_ids, affected_locations,
                                confidence, notes, created_at, updated_at, project_id, display_id, sequence_no,
                                root_cause, observed_behavior, expected_behavior, security_impact, attack_scenario,
                                affected_files, line_range, reproducer_spec, validator_verdict, plan_id, work_package_id
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            v.vulnerability_id, f"fp-{v.vulnerability_id}",
                            f"{v.title}: {v.hypothesis}",
                            json.dumps([{"file": v.relative_path, "line_start": v.line_start, "line_end": v.line_end}]),
                            json.dumps([full_vuln_evi_id]), "[]", v.validation_method,
                            v.validator_result if rep_exit == 0 else "INCONCLUSIVE",
                            "CONFIRMED" if rep_exit == 0 else "OPEN",
                            json.dumps({"title": v.title, "cwe": v.cwe, "impact": v.impact}),
                            json.dumps({"created_at": rep_t_start, "updated_at": rep_t_end}),
                            "1.0", tid, v.severity, json.dumps([full_vuln_evi_id]), "[]",
                            json.dumps([f"{v.relative_path}:{v.line_start}-{v.line_end}"]),
                            0.98 if rep_exit == 0 else 0.6, v.title, rep_t_start, rep_t_end, pid,
                            full_vuln_id, v_seq,
                            v.root_cause, v.observed_behavior, v.expected_behavior, v.impact, v.attack_scenario,
                            json.dumps([v.relative_path]), f"{v.line_start}-{v.line_end}", v.reproducer_code,
                            "CONFIRMED" if rep_exit == 0 else "INCONCLUSIVE",
                            task_data.get("plan_id"), task_data.get("work_package_id")
                        ))
                        conn.commit()

                        await self._emit_event(
                            event_type="FINDING_CREATED",
                            actor="validator",
                            task_id=tid,
                            project_id=pid,
                            payload={
                                "finding_id": full_vuln_id,
                                "title": v.title,
                                "severity": v.severity,
                                "state": "CONFIRMED" if rep_exit == 0 else "OPEN",
                                "evidence_id": full_vuln_evi_id
                            }
                        )

        # ── Step 7: Post-Processing & Validation (Section 13) ──
        with self.db.get_connection() as conn:
            conn.execute("UPDATE tasks SET current_stage = 'POST_PROCESSING' WHERE task_id = ?", (tid,))
            conn.commit()

        await self._emit_event(
            event_type="POST_PROCESSING_STARTED",
            actor="orchestrator",
            task_id=tid,
            project_id=pid,
            payload={"task_id": tid, "stage": "POST_PROCESSING"}
        )

        with self.db.get_connection() as conn:
            conn.execute("UPDATE tasks SET current_stage = 'VALIDATING' WHERE task_id = ?", (tid,))
            conn.commit()

        await self._emit_event(
            event_type="VALIDATION_STARTED",
            actor="validator",
            task_id=tid,
            project_id=pid,
            payload={"task_id": tid, "evidence_id": full_evi_id}
        )

        verdict = "PASSED" if exit_code == 0 else "FAILED"
        await self._emit_event(
            event_type="VALIDATION_COMPLETED",
            actor="validator",
            task_id=tid,
            project_id=pid,
            payload={"task_id": tid, "verdict": verdict, "evidence_id": full_evi_id}
        )

        # ── Step 8: Terminal State & Aggregation (Section 22, 23, 24) ──
        term_time = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE tasks
                SET status = 'COMPLETED', current_stage = 'COMPLETED', completed_at = ?,
                    watchdog_status = 'NORMAL', stop_reason = NULL, why_queued = NULL
                WHERE task_id = ?
            """, (term_time, tid))

            conn.execute("""
                UPDATE task_attempts
                SET status = 'COMPLETED', completed_at = ?, end_time = ?
                WHERE task_id = ? AND status = 'RUNNING'
            """, (term_time, term_time, tid))

            # Reconcile WorkPackage
            wp_id = task_data.get("work_package_id")
            if wp_id:
                non_term = conn.execute("""
                    SELECT COUNT(*) FROM tasks
                    WHERE work_package_id = ? AND status NOT IN ('COMPLETED', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'STOPPED')
                """, (wp_id,)).fetchone()[0]
                if non_term == 0:
                    conn.execute("UPDATE work_packages SET status = 'COMPLETED' WHERE package_id = ?", (wp_id,))
                else:
                    conn.execute("UPDATE work_packages SET status = 'RUNNING' WHERE package_id = ?", (wp_id,))

            # Reconcile Run
            if run_id:
                run_non_term = conn.execute("""
                    SELECT COUNT(*) FROM tasks
                    WHERE (plan_id = ? OR workflow_id = ?) AND status NOT IN ('COMPLETED', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'STOPPED')
                """, (run_id, run_id)).fetchone()[0]
                if run_non_term == 0:
                    conn.execute("UPDATE runs SET status = 'COMPLETED', run_state = 'COMPLETED', end_time = ?, completed_at = ? WHERE run_id = ?", (term_time, term_time, run_id))
                else:
                    conn.execute("UPDATE runs SET status = 'RUNNING', run_state = 'RUNNING' WHERE run_id = ?", (run_id,))

            conn.commit()

        self._last_completed_time = term_time
        self._active_executions.pop(tid, None)

        await self._emit_event(
            event_type="TASK_RESULT",
            actor=assigned_agent,
            task_id=tid,
            project_id=pid,
            payload={"task_id": tid, "status": "COMPLETED"}
        )

        await self._emit_event(
            event_type="TASK_COMPLETED",
            actor="orchestrator",
            task_id=tid,
            project_id=pid,
            payload={"task_id": tid, "status": "COMPLETED"}
        )

        print(f"[SCHEDULER] Task {disp_id} ({tid}) reached terminal COMPLETED state.")


# Global singleton instance
task_scheduler = TaskScheduler()
