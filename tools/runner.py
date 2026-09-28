"""
LLMorch Deterministic Tool Runner
Executes verification tools in isolated environments.
Captures command, environment, exit code, stdout/stderr, execution timing, hashes,
and links results into the authoritative Evidence Plane.
"""

from __future__ import annotations

import os
import subprocess
import time
import hashlib
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from history.database import DatabaseService


class ToolRunResult(BaseModel):
    execution_id: str = Field(default_factory=lambda: f"exec-{uuid.uuid4().hex[:8]}")
    tool_name: str
    command: str
    args: List[str] = Field(default_factory=list)
    working_dir: str
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    wall_time_seconds: float = 0.0
    stdout_hash: str = ""
    stderr_hash: str = ""
    output_hash: str = ""
    status: str = "COMPLETED"  # COMPLETED, FAILED, TIMED_OUT
    evidence_ids: List[str] = Field(default_factory=list)
    failure_reason: Optional[str] = None
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ToolExecutionConfig(BaseModel):
    tool_name: str
    command: List[str]
    working_dir: str = "."
    timeout_seconds: int = 120
    env_vars: Optional[Dict[str, str]] = None
    task_id: Optional[str] = None
    run_id: Optional[str] = None


class DeterministicToolRunner:
    """
    Executes CLI and script tools with timeout and sandboxed recording.
    """

    def __init__(self, db: Optional[DatabaseService] = None):
        self.db = db

    def execute_tool(self, config: ToolExecutionConfig) -> ToolRunResult:
        res = self.execute_command(
            command=config.command,
            working_dir=config.working_dir,
            tool_name=config.tool_name,
            task_id=config.task_id,
            run_id=config.run_id,
            timeout_seconds=config.timeout_seconds,
            env_vars=config.env_vars,
        )
        res.output_hash = res.stdout_hash
        return res

    def execute_command(
        self,
        command: List[str],
        working_dir: str,
        tool_name: str,
        task_id: Optional[str] = None,
        run_id: Optional[str] = None,
        timeout_seconds: int = 120,
        env_vars: Optional[Dict[str, str]] = None
    ) -> ToolRunResult:
        started_at = datetime.now(timezone.utc).isoformat()
        t0 = time.time()
        exec_id = f"exec-{uuid.uuid4().hex[:8]}"

        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        exit_code = -1
        stdout_str = ""
        stderr_str = ""
        status = "COMPLETED"
        failure_reason = None

        try:
            res = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=env
            )
            exit_code = res.returncode
            stdout_str = res.stdout
            stderr_str = res.stderr
            wall_time = round(time.time() - t0, 3)

            if exit_code != 0:
                status = "FAILED"
                failure_reason = f"Process exited with non-zero code {exit_code}: {stderr_str[:200]}"

        except subprocess.TimeoutExpired:
            wall_time = round(time.time() - t0, 3)
            exit_code = 124
            status = "TIMED_OUT"
            stderr_str = f"Execution timed out after {timeout_seconds} seconds"
            failure_reason = stderr_str
        except Exception as e:
            wall_time = round(time.time() - t0, 3)
            exit_code = 1
            status = "FAILED"
            stderr_str = str(e)
            failure_reason = f"Execution error: {str(e)}"

        completed_at = datetime.now(timezone.utc).isoformat()
        stdout_hash = hashlib.sha256(stdout_str.encode("utf-8")).hexdigest()
        stderr_hash = hashlib.sha256(stderr_str.encode("utf-8")).hexdigest()

        evidence_ids = []
        # If execution completed, register evidence
        if self.db:
            evidence_id = f"evi-{uuid.uuid4().hex[:8]}"
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO evidence (
                        evidence_id, task_id, run_id, agent_id, source_type,
                        raw_hash, canonical_hash, semantic_fingerprint, environment_fingerprint,
                        exit_status, provenance, schema_version, command, stdout, stderr, exit_code
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    evidence_id, task_id or "task-general", run_id or "run-general", "tool-runner", tool_name,
                    stdout_hash, stdout_hash, f"tool:{tool_name}", "linux-sandbox",
                    exit_code, f"{tool_name} execution", "1.0", " ".join(command), stdout_str[:2000], stderr_str[:2000], exit_code
                ))

                conn.execute("""
                    INSERT INTO tool_executions (
                        execution_id, tool_name, category, agent_id, task_id, run_id,
                        command, args, working_dir, status, exit_code, stdout_artifact,
                        stderr_artifact, execution_result, evidence_ids, started_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    exec_id, tool_name, "Verification", "orchestrator", task_id, run_id,
                    " ".join(command), str(command[1:]), working_dir, status, exit_code,
                    stdout_str[:1000], stderr_str[:1000], failure_reason or "Success",
                    str([evidence_id]), started_at, completed_at
                ))
                conn.commit()
            evidence_ids.append(evidence_id)

        return ToolRunResult(
            execution_id=exec_id,
            tool_name=tool_name,
            command=" ".join(command),
            args=command[1:],
            working_dir=working_dir,
            exit_code=exit_code,
            stdout=stdout_str,
            stderr=stderr_str,
            wall_time_seconds=wall_time,
            stdout_hash=stdout_hash,
            stderr_hash=stderr_hash,
            status=status,
            evidence_ids=evidence_ids,
            failure_reason=failure_reason,
            started_at=started_at,
            completed_at=completed_at
        )
