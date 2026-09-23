"""
LLMorch Adapters - Real Antigravity CLI Execution Boundary Implementation
Invokes installed Antigravity CLI via process isolation/subprocess supervision,
handles input formatting, stdout/stderr streaming, process cancellation, and normalization into TaskResult.
"""

import os
import sys
import json
import shutil
import subprocess
import signal
import hashlib
from typing import List, Generator, Any, Dict, Optional
from datetime import datetime
from pathlib import Path

from .base import BaseAgentAdapter
from schemas.task import Task
from schemas.run import Run, RunStatus
from schemas.event import Event, EventType
from schemas.artifact import Artifact, ArtifactType, RetentionClass
from schemas.health import AgentHealthState
from schemas.capability import AgentCapability
from schemas.task_result import TaskResult


class AGYAdapter(BaseAgentAdapter):
    """
    Provider-neutral adapter implementation for real Antigravity CLI subprocess execution.
    """

    def __init__(self, cli_executable: Optional[str] = None, config_override: Optional[Dict[str, Any]] = None):
        self.cli_executable = cli_executable or self._detect_cli_executable()
        self.config = config_override or {"model_alias": "runtime-resolved", "timeout": 3600}
        self.active_processes: Dict[str, subprocess.Popen] = {}
        self.active_runs: Dict[str, Run] = {}

    def _detect_cli_executable(self) -> str:
        """Detects available Antigravity CLI binary on the host system."""
        candidates = ["antigravity-cli", "antigravity", "agy"]
        for candidate in candidates:
            path = shutil.which(candidate)
            if path:
                return path
        return "antigravity"

    def start(self, task: Task) -> Run:
        """Starts real Antigravity process attempt for given Task."""
        run = Run(
            task_id=task.task_id,
            agent_id="agent-agy-01",
            adapter_version=self.version(),
            workspace_id=task.workspace_policy.allowed_paths[0] if task.workspace_policy.allowed_paths else "ws-default",
            environment_fingerprint=f"env-{hashlib.sha256(self.cli_executable.encode()).hexdigest()[:12]}",
            status=RunStatus.RUNNING,
            start_time=datetime.utcnow()
        )
        self.active_runs[run.run_id] = run
        return run

    def execute_task_sync(self, task: Task, workspace_dir: str, context_prompt: str) -> Dict[str, Any]:
        """
        Launches real Antigravity process synchronously with process-group supervision.
        Returns execution outcome dictionary (exit_code, stdout, stderr, process_id).
        """
        run = self.start(task)
        cmd = [self.cli_executable, "--prompt", context_prompt]

        # Ensure working directory is workspace
        cwd = workspace_dir if os.path.exists(workspace_dir) else os.getcwd()

        try:
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid # Create new process group for clean cancellation
            )
            run.process_id = process.pid
            self.active_processes[run.run_id] = process

            stdout, stderr = process.communicate(timeout=task.budget.max_seconds)
            exit_code = process.returncode

            run.end_time = datetime.utcnow()
            run.exit_status = exit_code
            run.status = RunStatus.SUCCEEDED if exit_code == 0 else RunStatus.FAILED

            return {
                "run_id": run.run_id,
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "process_id": process.pid,
                "run": run
            }
        except subprocess.TimeoutExpired:
            self._kill_process_group(run.run_id)
            run.status = RunStatus.TIMEOUT
            run.end_time = datetime.utcnow()
            run.failure_reason = "Execution timed out"
            return {
                "run_id": run.run_id,
                "exit_code": -1,
                "stdout": "",
                "stderr": "Execution timed out",
                "process_id": run.process_id,
                "run": run
            }
        except Exception as e:
            run.status = RunStatus.FAILED
            run.end_time = datetime.utcnow()
            run.failure_reason = str(e)
            return {
                "run_id": run.run_id,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "process_id": None,
                "run": run
            }

    def _kill_process_group(self, run_id: str):
        process = self.active_processes.get(run_id)
        if process and process.poll() is None:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except Exception:
                pass

    def stream(self, run_id: str) -> Generator[Event, None, None]:
        if run_id not in self.active_runs:
            return
        yield Event(
            run_id=run_id,
            event_type=EventType.AGENT_STARTED,
            actor="agent-agy-01",
            payload={"cli_executable": self.cli_executable}
        )

    def cancel(self, task_id: str) -> bool:
        for run_id, run in list(self.active_runs.items()):
            if run.task_id == task_id and run.status == RunStatus.RUNNING:
                self._kill_process_group(run_id)
                run.status = RunStatus.CANCELLED
                run.end_time = datetime.utcnow()
                return True
        return False

    def health(self) -> AgentHealthState:
        if shutil.which(self.cli_executable):
            return AgentHealthState.AVAILABLE
        return AgentHealthState.UNAVAILABLE

    def capabilities(self) -> List[str]:
        return [
            AgentCapability.REPOSITORY_ANALYSIS.value,
            AgentCapability.CODE_ANALYSIS.value,
            AgentCapability.RTL_ANALYSIS.value,
            AgentCapability.SOFTWARE_ANALYSIS.value,
            AgentCapability.DEBUGGING.value,
            AgentCapability.SHELL_EXECUTION.value,
            AgentCapability.TEST_GENERATION.value,
            AgentCapability.REPRODUCER_GENERATION.value,
            AgentCapability.STATIC_ANALYSIS.value,
            AgentCapability.DOCUMENTATION_ANALYSIS.value,
            AgentCapability.SECURITY_REVIEW.value,
        ]

    def collect_artifacts(self, run_id: str) -> List[Artifact]:
        return []

    def normalize_result(self, raw_output: Any) -> TaskResult:
        """
        Parses raw text/JSON stdout from Antigravity into structured TaskResult contract.
        """
        raw_text = str(raw_output)
        hypothesis = "Security vulnerability hypothesis under evaluation"
        locations = []
        confidence = 0.8
        status = "SUCCEEDED"

        # Attempt JSON parse if output is structured JSON
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                hypothesis = parsed.get("hypothesis", hypothesis)
                locations = parsed.get("affected_locations", locations)
                confidence = float(parsed.get("confidence", confidence))
                status = parsed.get("status", status)
        except Exception:
            # Natural language fallback extraction
            for line in raw_text.splitlines():
                if "hypothesis:" in line.lower():
                    hypothesis = line.split(":", 1)[1].strip()
                elif "location:" in line.lower():
                    loc_str = line.split(":", 1)[1].strip()
                    locations.append({"file_path": loc_str})

        return TaskResult(
            task_id="task-unknown",
            run_id="run-unknown",
            status=status,
            hypothesis=hypothesis,
            affected_locations=locations,
            confidence=confidence
        )

    def version(self) -> str:
        return "1.0.0"

    def configuration(self) -> Dict[str, Any]:
        return self.config

    def workspace_requirements(self) -> Dict[str, Any]:
        return {
            "isolation": "process",
            "mount_point": "/home/hackdac/Desktop/intern/LLMorch",
            "read_only": False,
        }
