"""
LLMorch — Project-Scoped Development Logger.
Section 45, 46, 47, 48:
Provides isolated logging per project:
logs/
  projects/
    <project_id>/
      project.log
      intake.log
      orchestrator.log
      realtime.log
      errors.log
      runs/
        <run_id>/
          run.log
          agents/
            <agent_id>.log
          tools/
            <tool_id>.log
          execution.jsonl
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
LOGS_ROOT = WORKSPACE_ROOT / "logs" / "projects"


class ProjectLogger:
    """Manages project-isolated log files and structured event streams."""

    @staticmethod
    def _ensure_dir(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_project_log_dir(cls, project_id: str) -> Path:
        safe_id = "".join(c for c in project_id if c.isalnum() or c in ("-", "_"))
        return cls._ensure_dir(LOGS_ROOT / safe_id)

    @classmethod
    def get_run_log_dir(cls, project_id: str, run_id: str) -> Path:
        p_dir = cls.get_project_log_dir(project_id)
        safe_run = "".join(c for c in run_id if c.isalnum() or c in ("-", "_"))
        return cls._ensure_dir(p_dir / "runs" / safe_run)

    @classmethod
    def _write_log(cls, file_path: Path, message: str, level: str = "INFO", extra: Optional[Dict[str, Any]] = None):
        try:
            cls._ensure_dir(file_path.parent)
            ts = datetime.now(timezone.utc).isoformat()
            extra_str = f" | {json.dumps(extra)}" if extra else ""
            line = f"[{ts}] [{level}] {message}{extra_str}\n"
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    @classmethod
    def log_project(cls, project_id: str, message: str, level: str = "INFO", extra: Optional[Dict[str, Any]] = None):
        p_dir = cls.get_project_log_dir(project_id)
        cls._write_log(p_dir / "project.log", message, level, extra)

    @classmethod
    def log_intake(cls, project_id: str, message: str, level: str = "INFO", extra: Optional[Dict[str, Any]] = None):
        p_dir = cls.get_project_log_dir(project_id)
        cls._write_log(p_dir / "intake.log", message, level, extra)

    @classmethod
    def log_orchestrator(cls, project_id: str, message: str, run_id: Optional[str] = None, task_id: Optional[str] = None, level: str = "INFO", extra: Optional[Dict[str, Any]] = None):
        p_dir = cls.get_project_log_dir(project_id)
        payload = dict(extra or {})
        if run_id: payload["run_id"] = run_id
        if task_id: payload["task_id"] = task_id
        cls._write_log(p_dir / "orchestrator.log", message, level, payload)
        if run_id:
            r_dir = cls.get_run_log_dir(project_id, run_id)
            cls._write_log(r_dir / "run.log", message, level, payload)

    @classmethod
    def log_realtime(cls, project_id: str, event_type: str, payload: Optional[Dict[str, Any]] = None, client_id: Optional[str] = None):
        p_dir = cls.get_project_log_dir(project_id)
        extra = {"event_type": event_type}
        if client_id: extra["client_id"] = client_id
        if payload: extra["payload"] = payload
        cls._write_log(p_dir / "realtime.log", f"EVENT: {event_type}", "INFO", extra)

    @classmethod
    def log_error(cls, project_id: str, error_message: str, run_id: Optional[str] = None, task_id: Optional[str] = None, exc_info: Optional[str] = None):
        p_dir = cls.get_project_log_dir(project_id)
        extra = {}
        if run_id: extra["run_id"] = run_id
        if task_id: extra["task_id"] = task_id
        if exc_info: extra["exc_info"] = str(exc_info)
        cls._write_log(p_dir / "errors.log", error_message, "ERROR", extra)
        if run_id:
            r_dir = cls.get_run_log_dir(project_id, run_id)
            cls._write_log(r_dir / "run.log", error_message, "ERROR", extra)

    @classmethod
    def log_tool_execution(
        cls,
        project_id: str,
        run_id: str,
        tool_id: str,
        command: str,
        exit_code: int,
        duration_ms: float,
        stdout_snippet: Optional[str] = None,
        stderr_snippet: Optional[str] = None,
        task_id: Optional[str] = None
    ):
        r_dir = cls.get_run_log_dir(project_id, run_id)
        tools_dir = cls._ensure_dir(r_dir / "tools")
        safe_tool = "".join(c for c in tool_id if c.isalnum() or c in ("-", "_"))
        t_file = tools_dir / f"{safe_tool}.log"
        extra = {
            "tool_id": tool_id,
            "task_id": task_id,
            "command": command,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "stdout": stdout_snippet[:500] if stdout_snippet else None,
            "stderr": stderr_snippet[:500] if stderr_snippet else None
        }
        cls._write_log(t_file, f"Execution exit={exit_code} dur={duration_ms:.1f}ms: {command}", "INFO", extra)

        # Append to execution.jsonl
        cls.append_execution_jsonl(project_id, run_id, {
            "type": "TOOL_EXECUTION",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_id": tool_id,
            "task_id": task_id,
            "command": command,
            "exit_code": exit_code,
            "duration_ms": duration_ms
        })

    @classmethod
    def log_agent_execution(
        cls,
        project_id: str,
        run_id: str,
        agent_id: str,
        task_id: str,
        attempt_id: str,
        role: str,
        model: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        r_dir = cls.get_run_log_dir(project_id, run_id)
        agents_dir = cls._ensure_dir(r_dir / "agents")
        safe_agent = "".join(c for c in agent_id if c.isalnum() or c in ("-", "_"))
        a_file = agents_dir / f"{safe_agent}.log"
        extra = {
            "agent_id": agent_id,
            "task_id": task_id,
            "attempt_id": attempt_id,
            "role": role,
            "model": model,
            "metadata": metadata or {}
        }
        cls._write_log(a_file, message, "INFO", extra)

        # Append to execution.jsonl
        cls.append_execution_jsonl(project_id, run_id, {
            "type": "AGENT_ACTIVITY",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": agent_id,
            "task_id": task_id,
            "attempt_id": attempt_id,
            "role": role,
            "model": model,
            "message": message
        })

    @classmethod
    def append_execution_jsonl(cls, project_id: str, run_id: str, record: Dict[str, Any]):
        try:
            r_dir = cls.get_run_log_dir(project_id, run_id)
            jsonl_file = r_dir / "execution.jsonl"
            with open(jsonl_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass

    @classmethod
    def get_logs_summary(cls, project_id: str) -> Dict[str, Any]:
        """Returns summary of available project log files and recent lines."""
        p_dir = cls.get_project_log_dir(project_id)
        result = {"project_id": project_id, "logs": {}}
        for log_name in ("project.log", "intake.log", "orchestrator.log", "realtime.log", "errors.log"):
            lp = p_dir / log_name
            if lp.exists():
                lines = lp.read_text(encoding="utf-8", errors="ignore").splitlines()
                result["logs"][log_name] = {
                    "exists": True,
                    "total_lines": len(lines),
                    "recent": lines[-25:]
                }
            else:
                result["logs"][log_name] = {"exists": False, "total_lines": 0, "recent": []}
        return result
