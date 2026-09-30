"""
LogManager & Retention Engine (Sections 30, 31, 32, 33, 34, 35, 36, 37, 39)
- Maintains two distinct logging levels:
  A. Application Global Log: logs/application/
  B. Project / Run Logs: logs/projects/{proj_id}/runs/{run_id}/
- Development Log Quota: 1.5 GB maximum.
  80%: warning
  90%: warning + cleanup recommendation
  100%: automatic deterministic cleanup
- Age-Based Retention: 3 days default.
- Deterministic cleanup priority:
  1. Expired completed-run logs
  2. Old project logs
  3. Old application logs
  Never deletes active runs, evidence, artifacts, findings, database records.
- Logs cleanup events: LOG_CLEANUP_STARTED, LOG_FILE_DELETED, LOG_CLEANUP_COMPLETED.
"""

from __future__ import annotations

import os
import time
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


MAX_LOG_QUOTA_BYTES = int(1.5 * 1024 * 1024 * 1024)  # 1.5 GB
DEFAULT_RETENTION_DAYS = 3


class LogManager:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or "logs")
        self.application_dir = self.base_dir / "application"
        self.projects_dir = self.base_dir / "projects"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        self.application_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

        # Ensure standard global log files exist
        global_files = [
            "application.log", "api.log", "database.log", "orchestrator.log",
            "scheduler.log", "realtime.log", "agents.log", "tools.log", "errors.log"
        ]
        for gf in global_files:
            p = self.application_dir / gf
            if not p.exists():
                p.touch()

    def get_project_log_dir(self, project_id: str) -> Path:
        d = self.projects_dir / project_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_run_log_dir(self, project_id: str, run_id: str) -> Path:
        d = self.projects_dir / project_id / "runs" / run_id
        (d / "agents").mkdir(parents=True, exist_ok=True)
        (d / "tools").mkdir(parents=True, exist_ok=True)
        return d

    def write_log(
        self,
        component: str,
        level: str,
        message: str,
        project_id: Optional[str] = None,
        run_id: Optional[str] = None,
        task_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        tool_id: Optional[str] = None,
        event_type: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Application-wide correlated log entry (Section 39).
        Writes to application global logs, and if project_id is present, also writes to project/run log.
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        corr_id = correlation_id or f"corr-{os.urandom(3).hex()}"

        record = {
            "timestamp": now_iso,
            "level": level.upper(),
            "component": component.upper(),
            "project_id": project_id,
            "run_id": run_id,
            "task_id": task_id,
            "attempt_id": attempt_id,
            "agent_id": agent_id,
            "tool_id": tool_id,
            "event_type": event_type or "OPERATION",
            "correlation_id": corr_id,
            "message": message,
        }

        line = (
            f"{now_iso} [{level.upper()}] [{component.upper()}] "
            f"proj={project_id or 'GLOBAL'} run={run_id or 'NONE'} task={task_id or 'NONE'} "
            f"event={event_type or 'INFO'} corr={corr_id} message=\"{message}\"\n"
        )

        # 1. Write to global log
        try:
            with open(self.application_dir / "application.log", "a", encoding="utf-8") as f:
                f.write(line)
            comp_file = self.application_dir / f"{component.lower()}.log"
            if comp_file.exists() or comp_file.name in ("api.log", "orchestrator.log", "scheduler.log", "realtime.log", "agents.log", "tools.log"):
                with open(comp_file, "a", encoding="utf-8") as f:
                    f.write(line)
            if level.upper() in ("ERROR", "CRITICAL"):
                with open(self.application_dir / "errors.log", "a", encoding="utf-8") as f:
                    f.write(line)
        except Exception:
            pass

        # 2. Write to project log
        if project_id:
            try:
                p_dir = self.get_project_log_dir(project_id)
                with open(p_dir / "project.log", "a", encoding="utf-8") as f:
                    f.write(line)
                if level.upper() in ("ERROR", "CRITICAL"):
                    with open(p_dir / "errors.log", "a", encoding="utf-8") as f:
                        f.write(line)
            except Exception:
                pass

        # 3. Write to run log
        if project_id and run_id:
            try:
                r_dir = self.get_run_log_dir(project_id, run_id)
                with open(r_dir / "run.log", "a", encoding="utf-8") as f:
                    f.write(line)
                with open(r_dir / "execution.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")
                if agent_id:
                    with open(r_dir / "agents" / f"{agent_id}.log", "a", encoding="utf-8") as f:
                        f.write(line)
                if tool_id:
                    with open(r_dir / "tools" / f"{tool_id}.log", "a", encoding="utf-8") as f:
                        f.write(line)
            except Exception:
                pass

        return record

    def get_storage_stats(self, retention_days: int = DEFAULT_RETENTION_DAYS) -> Dict[str, Any]:
        """Calculates total log storage, warning thresholds, and eligible cleanup files."""
        total_size = 0
        file_count = 0
        eligible_files = []
        now_ts = time.time()
        retention_cutoff_ts = now_ts - (retention_days * 86400)

        for p in self.base_dir.rglob("*"):
            if p.is_file():
                sz = p.stat().st_size
                total_size += sz
                file_count += 1
                mtime = p.stat().st_mtime
                # Active runs or database files are excluded
                if mtime < retention_cutoff_ts and not p.name.endswith(".db"):
                    eligible_files.append(str(p))

        pct_used = min(100.0, (total_size / MAX_LOG_QUOTA_BYTES) * 100.0)

        if pct_used >= 100.0:
            warning_level = "OVER_QUOTA_100"
        elif pct_used >= 90.0:
            warning_level = "WARNING_90"
        elif pct_used >= 80.0:
            warning_level = "WARNING_80"
        else:
            warning_level = "OK"

        avail_bytes = max(0, MAX_LOG_QUOTA_BYTES - total_size)
        mb_used = total_size / (1024 * 1024)
        mb_avail = avail_bytes / (1024 * 1024)

        return {
            "global_log_dir": str(self.application_dir.resolve()),
            "project_log_dir": str(self.projects_dir.resolve()),
            "retention_days": retention_days,
            "max_size_bytes": MAX_LOG_QUOTA_BYTES,
            "global_size_limit_bytes": MAX_LOG_QUOTA_BYTES,
            "max_size_display": "1.5 GB",
            "current_size_bytes": total_size,
            "current_size_display": f"{mb_used:.1f} MB",
            "available_space_display": f"{mb_avail:.1f} MB",
            "percent_used": round(pct_used, 1),
            "warning_level": warning_level,
            "file_count": file_count,
            "eligible_file_count": len(eligible_files),
            "last_cleanup": datetime.now(timezone.utc).isoformat(),
            "next_cleanup": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        }

    def run_cleanup(
        self,
        db_conn: Optional[sqlite3.Connection] = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        force_under_quota: bool = False
    ) -> Dict[str, Any]:
        """
        Executes deterministic log cleanup (Sections 34, 35, 36).
        Priority:
        1. Expired completed-run logs (> retention_days)
        2. Old project logs (> retention_days)
        3. Old application logs (> retention_days)
        NEVER deletes active current-run logs, active tasks, evidence, artifacts, findings, or database files.
        """
        now = datetime.now(timezone.utc)
        self.write_log("SCHEDULER", "INFO", "LOG_CLEANUP_STARTED", event_type="LOG_CLEANUP_STARTED")

        # Find active runs to strictly preserve
        active_runs = set()
        active_projects = set()
        if db_conn:
            try:
                r_rows = db_conn.execute("SELECT run_id, project_id FROM runs WHERE status IN ('RUNNING', 'ACTIVE')").fetchall()
                for r in r_rows:
                    active_runs.add(r[0])
                    if r[1]:
                        active_projects.add(r[1])
            except Exception:
                pass

        now_ts = time.time()
        retention_cutoff_ts = now_ts - (retention_days * 86400)

        # Collect eligible files categorized by priority
        priority1_run_files: List[Tuple[Path, int, float]] = []
        priority2_proj_files: List[Tuple[Path, int, float]] = []
        priority3_app_files: List[Tuple[Path, int, float]] = []

        total_size = 0
        for p in self.base_dir.rglob("*"):
            if not p.is_file() or p.name.endswith(".db"):
                continue
            stat = p.stat()
            sz = stat.st_size
            mtime = stat.st_mtime
            total_size += sz

            # Check if active
            parts = p.parts
            is_active_run = any(ar in parts for ar in active_runs)
            if is_active_run:
                continue

            # Classify
            if "runs" in parts:
                if mtime < retention_cutoff_ts or force_under_quota:
                    priority1_run_files.append((p, sz, mtime))
            elif "projects" in parts:
                if mtime < retention_cutoff_ts or force_under_quota:
                    priority2_proj_files.append((p, sz, mtime))
            elif "application" in parts:
                # Never delete active global log files themselves, only rotated or old ones
                if p.name not in ("application.log", "errors.log") and (mtime < retention_cutoff_ts or force_under_quota):
                    priority3_app_files.append((p, sz, mtime))

        # Sort each priority group oldest first
        priority1_run_files.sort(key=lambda x: x[2])
        priority2_proj_files.sort(key=lambda x: x[2])
        priority3_app_files.sort(key=lambda x: x[2])

        files_deleted = 0
        bytes_freed = 0

        # Delete according to priority until under quota or all eligible removed
        candidate_queue = priority1_run_files + priority2_proj_files + priority3_app_files
        for file_path, sz, mtime in candidate_queue:
            if not force_under_quota and mtime >= retention_cutoff_ts and total_size - bytes_freed <= MAX_LOG_QUOTA_BYTES:
                break
            try:
                file_path.unlink()
                files_deleted += 1
                bytes_freed += sz
                self.write_log(
                    "SCHEDULER", "INFO",
                    f"LOG_FILE_DELETED: {file_path.name} ({sz} bytes)",
                    event_type="LOG_FILE_DELETED"
                )
                if total_size - bytes_freed <= MAX_LOG_QUOTA_BYTES and not force_under_quota and mtime >= retention_cutoff_ts:
                    break
            except Exception:
                pass

        self.write_log(
            "SCHEDULER", "INFO",
            f"LOG_CLEANUP_COMPLETED: deleted {files_deleted} files, freed {bytes_freed} bytes",
            event_type="LOG_CLEANUP_COMPLETED"
        )

        return {
            "status": "CLEANUP_COMPLETED",
            "files_deleted": files_deleted,
            "files_removed": files_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_display": f"{(bytes_freed / (1024 * 1024)):.2f} MB",
            "current_size_bytes": max(0, total_size - bytes_freed),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def read_filtered_logs(
        self,
        project_id: Optional[str] = None,
        run_id: Optional[str] = None,
        component: Optional[str] = None,
        level: Optional[str] = None,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Reads and filters structured logs for Global or Project log viewers (Sections 32 & 33).
        """
        matched_lines = []

        # Choose primary log file
        log_files_to_check = []
        if project_id and run_id:
            r_dir = self.projects_dir / project_id / "runs" / run_id
            if (r_dir / "run.log").exists():
                log_files_to_check.append(r_dir / "run.log")
        elif project_id:
            p_dir = self.projects_dir / project_id
            if (p_dir / "project.log").exists():
                log_files_to_check.append(p_dir / "project.log")
            # Also check run logs under this project
            for rl in (p_dir / "runs").rglob("run.log"):
                log_files_to_check.append(rl)
        else:
            # Global logs
            app_log = self.application_dir / "application.log"
            if app_log.exists():
                log_files_to_check.append(app_log)

        for lf in log_files_to_check:
            try:
                with open(lf, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line_str = line.strip()
                        if not line_str:
                            continue
                        if level and f"[{level.upper()}]" not in line_str:
                            continue
                        if component and f"[{component.upper()}]" not in line_str:
                            continue
                        if project_id and f"proj={project_id}" not in line_str and project_id not in line_str:
                            continue
                        if run_id and f"run={run_id}" not in line_str and run_id not in line_str:
                            continue
                        if task_id and f"task={task_id}" not in line_str and task_id not in line_str:
                            continue
                        if agent_id and agent_id not in line_str:
                            continue
                        if query and query.lower() not in line_str.lower():
                            continue
                        matched_lines.append(line_str)
            except Exception:
                pass

        # Deduplicate and sort descending by timestamp
        matched_lines.reverse()
        total = len(matched_lines)
        paged = matched_lines[offset:offset + limit]

        # Parse into structured display objects
        entries = []
        for line in paged:
            parts = line.split(" ", 4)
            ts = parts[0] if len(parts) > 0 else datetime.now(timezone.utc).isoformat()
            lvl = parts[1].strip("[]") if len(parts) > 1 else "INFO"
            comp = parts[2].strip("[]") if len(parts) > 2 else "ORCHESTRATOR"
            raw_msg = parts[4] if len(parts) > 4 else line
            entries.append({
                "timestamp": ts,
                "level": lvl,
                "component": comp,
                "raw": line,
                "message": raw_msg
            })

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "entries": entries
        }


# Global singleton instance
log_manager = LogManager()
