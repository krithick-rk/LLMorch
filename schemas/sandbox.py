"""
LLMorch Data Contracts - Phase 8 Sandbox Execution & ExecutionTrace
Provides schemas for hardened execution modes, resource constraints, and machine-generated execution traces.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import hashlib
from pydantic import BaseModel, Field
import uuid


class SandboxMode(str, Enum):
    SAFE_READ_ONLY_ANALYSIS = "SAFE_READ_ONLY_ANALYSIS"
    CONTROLLED_BUILD = "CONTROLLED_BUILD"
    UNTRUSTED_REPRODUCTION = "UNTRUSTED_REPRODUCTION"
    FORMAL_VALIDATION = "FORMAL_VALIDATION"
    RTL_SIMULATION = "RTL_SIMULATION"
    FUZZING = "FUZZING"


class SandboxStatus(str, Enum):
    COMPLETED = "COMPLETED"
    SANDBOX_FAILED = "SANDBOX_FAILED"
    ENVIRONMENT_FAILED = "ENVIRONMENT_FAILED"
    TIMEOUT = "TIMEOUT"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    POLICY_BLOCKED = "POLICY_BLOCKED"


class SandboxPolicy(BaseModel):
    """Execution policy constraints enforced on sandbox launch."""
    mode: SandboxMode = SandboxMode.UNTRUSTED_REPRODUCTION
    allow_network: bool = Field(default=False, description="Default: strictly disabled")
    read_only_root: bool = Field(default=True, description="Default: host files read-only")
    writable_workspace: bool = Field(default=True, description="Only designated workspace is writable")
    cpu_timeout_seconds: int = Field(default=60, description="Execution timeout limit")
    timeout_seconds: Optional[float] = Field(default=None, description="Execution timeout override")
    max_memory_mb: int = Field(default=2048, description="Memory limit in MB")
    memory_limit_mb: Optional[int] = Field(default=None, description="Memory limit override")
    max_processes: int = Field(default=64, description="PID/process limit")
    environment_whitelist: List[str] = Field(
        default_factory=lambda: ["PATH", "HOME", "LANG", "LC_ALL"],
        description="Whitelisted env variables; all host secrets and credentials stripped"
    )
    blocked_paths: List[str] = Field(
        default_factory=lambda: [".ssh", ".aws", ".config", ".antigravity", ".claude", ".codex", ".gemini"],
        description="Forbidden path substrings denied to sandbox"
    )

    def get_effective_timeout(self) -> float:
        return float(self.timeout_seconds) if self.timeout_seconds is not None else float(self.cpu_timeout_seconds)


class ExecutionTrace(BaseModel):
    """
    Machine-generated audit trace produced directly by the Sandbox.
    Serves as authentic, untampered evidence for Validator evaluation.
    """
    trace_id: str = Field(default_factory=lambda: f"trc-{uuid.uuid4().hex[:12]}")
    sandbox_execution_id: str
    run_id: str
    reproducer_id: str
    command: List[str]
    tool_versions: Dict[str, str] = Field(default_factory=dict)
    start_time: datetime
    end_time: datetime
    wall_time_seconds: float
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    stdout_hash: str = ""
    stderr_hash: str = ""
    resource_usage: Dict[str, Any] = Field(default_factory=dict)
    network_policy: str = "DISABLED"
    environment_fingerprint: str = ""
    sandbox_backend: str = "bubblewrap"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        sandbox_execution_id: str,
        run_id: str,
        reproducer_id: str,
        command: List[str],
        tool_versions: Dict[str, str],
        start_time: datetime,
        end_time: datetime,
        exit_code: int,
        stdout: str,
        stderr: str,
        resource_usage: Dict[str, Any],
        sandbox_backend: str = "bubblewrap",
        network_policy: str = "DISABLED",
        env_fingerprint: str = ""
    ) -> "ExecutionTrace":
        wall_time = max((end_time - start_time).total_seconds(), 0.0)
        out_hash = hashlib.sha256(stdout.encode("utf-8", errors="replace")).hexdigest()
        err_hash = hashlib.sha256(stderr.encode("utf-8", errors="replace")).hexdigest()
        return cls(
            sandbox_execution_id=sandbox_execution_id,
            run_id=run_id,
            reproducer_id=reproducer_id,
            command=command,
            tool_versions=tool_versions,
            start_time=start_time,
            end_time=end_time,
            wall_time_seconds=wall_time,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            stdout_hash=out_hash,
            stderr_hash=err_hash,
            resource_usage=resource_usage,
            network_policy=network_policy,
            environment_fingerprint=env_fingerprint,
            sandbox_backend=sandbox_backend
        )


class SandboxResult(BaseModel):
    """Outcome of sandbox execution wrapper."""
    status: SandboxStatus
    trace: Optional[ExecutionTrace] = None
    error_message: Optional[str] = None
    is_policy_blocked: bool = False

    @property
    def exit_code(self) -> int:
        return self.trace.exit_code if self.trace is not None else -1

    @property
    def stdout(self) -> str:
        return self.trace.stdout if self.trace is not None else ""

    @property
    def stderr(self) -> str:
        return self.trace.stderr if self.trace is not None else (self.error_message or "")
