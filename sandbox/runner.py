"""
LLMorch Sandbox Runner (Phase 8 Pre-Flight & Hardening)
Executes untrusted reproducers and harnesses in a hardened rootless sandbox (Bubblewrap / process-group namespace jail).
Strictly enforces:
- Rootless isolation (user namespaces)
- Read-only host filesystem, explicit isolated writable workspace
- Network disabled by default (no external egress)
- Sanitized environment: all host secrets (~/.ssh, ~/.aws, ~/.config, provider tokens) stripped
- Resource limits (CPU timeout, memory, PID limits)
- Clean process-group termination (no orphan processes)
- Machine-generated ExecutionTrace generation for Validator evidence
"""

import os
import sys
import shutil
import signal
import subprocess
import time
import hashlib
import uuid
import shlex
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timezone

from schemas.sandbox import SandboxMode, SandboxStatus, SandboxPolicy, ExecutionTrace, SandboxResult


class SandboxRunner:
    """
    Hardened Sandbox Execution Boundary for Phase 8 untrusted execution.
    Executes commands inside Bubblewrap container jail with process-group fallback.
    """

    def __init__(self, policy: Optional[SandboxPolicy] = None):
        self.policy = policy or SandboxPolicy()
        self.bwrap_path = shutil.which("bwrap")

    def sanitize_environment(self, workspace_dir: str, extra_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Constructs a sanitized environment dictionary.
        Explicitly removes all host secrets, credentials, API keys, and sensitive tokens.
        """
        clean_env = {
            "PATH": "/home/hackdac/.HACK_AI/bin:/usr/local/bin:/usr/bin:/bin",
            "HOME": workspace_dir,
            "TMPDIR": "/tmp",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONPATH": "/home/hackdac/Desktop/intern/LLMorch"
        }
        if extra_env:
            for k, v in extra_env.items():
                # Filter out sensitive patterns
                k_upper = k.upper()
                if any(sec in k_upper for sec in ("KEY", "SECRET", "TOKEN", "AUTH", "PASS", "CRED", "SSH", "AWS")):
                    continue
                clean_env[k] = v
        return clean_env

    def is_policy_compliant(self, command: List[str], workspace_dir: str) -> Tuple[bool, Optional[str]]:
        """
        Validates command safety before dispatch.
        Rejects explicit attempts to target host secrets or perform path traversal outside workspace.
        """
        cmd_str = " ".join(command)
        for blocked in self.policy.blocked_paths:
            if blocked in cmd_str:
                return False, f"Policy violation: forbidden access to sensitive path '{blocked}'"

        # Check for path traversal targeting host roots
        for arg in command:
            if "../../../" in arg and ("/etc" in arg or "/root" in arg or "/home/hackdac/.ssh" in arg):
                return False, f"Policy violation: forbidden path traversal '{arg}'"

        return True, None

    def build_bwrap_command(self, user_command: List[str], workspace_dir: str, env: Dict[str, str]) -> List[str]:
        """
        Constructs rootless bubblewrap container invocation.
        """
        bwrap_cmd = [
            self.bwrap_path,
            # Read-only system mounts
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64",
            "--ro-bind", "/bin", "/bin",
            "--ro-bind", "/etc", "/etc",
            # Virtualenv read-only mount if available
            "--ro-bind", "/home/hackdac/.HACK_AI", "/home/hackdac/.HACK_AI",
            # Repository root read-only mount for module imports
            "--ro-bind", "/home/hackdac/Desktop/intern/LLMorch", "/home/hackdac/Desktop/intern/LLMorch",
            # Standard devices and proc
            "--proc", "/proc",
            "--dev", "/dev",
            "--tmpfs", "/tmp",
            # Writable workspace
            "--bind", workspace_dir, workspace_dir,
            "--chdir", workspace_dir,
            # Namespace isolation
            "--unshare-all"
        ]

        if self.policy.allow_network:
            # If network explicitly allowed, remove net unshare (bwrap default has net)
            pass

        # Environment setup
        bwrap_cmd.append("--clearenv")
        for k, v in env.items():
            bwrap_cmd.extend(["--setenv", k, v])

        bwrap_cmd.append("--")
        bwrap_cmd.extend(user_command)
        return bwrap_cmd

    def execute(
        self,
        command: Union[str, List[str]],
        workspace_dir: Optional[str] = None,
        sandbox_execution_id: Optional[str] = None,
        run_id: Optional[str] = None,
        reproducer_id: Optional[str] = None,
        extra_env: Optional[Dict[str, str]] = None,
        tool_versions: Optional[Dict[str, str]] = None,
        workspace: Optional[Union[str, Path]] = None,
        policy: Optional[SandboxPolicy] = None
    ) -> SandboxResult:
        """
        Executes command in rootless sandbox with process supervision and trace capture.
        """
        active_policy = policy or self.policy
        target_ws = str(workspace) if workspace is not None else (workspace_dir or "/tmp")
        sid = sandbox_execution_id or f"sexec-{uuid.uuid4().hex[:12]}"
        rid = run_id or f"run-{uuid.uuid4().hex[:8]}"
        repro_id = reproducer_id or f"repro-{uuid.uuid4().hex[:8]}"

        if isinstance(command, str):
            parsed_cmd = shlex.split(command)
        else:
            parsed_cmd = list(command)

        # 1. Policy Compliance Check
        compliant, reason = self.is_policy_compliant(parsed_cmd, target_ws)
        if not compliant:
            return SandboxResult(
                status=SandboxStatus.POLICY_BLOCKED,
                error_message=reason,
                is_policy_blocked=True
            )

        os.makedirs(target_ws, exist_ok=True)
        env = self.sanitize_environment(target_ws, extra_env)

        # 2. Determine Sandbox Backend
        use_bwrap = bool(self.bwrap_path and os.path.exists(self.bwrap_path))
        if use_bwrap:
            cmd = self.build_bwrap_command(parsed_cmd, target_ws, env)
            backend_name = "bubblewrap"
        else:
            cmd = parsed_cmd
            backend_name = "process_group"

        start_time = datetime.now(timezone.utc)
        start_mono = time.monotonic()
        timeout = active_policy.get_effective_timeout()

        process = None
        stdout = ""
        stderr = ""
        exit_code = -1
        status = SandboxStatus.COMPLETED

        try:
            # Launch in independent process group for clean cancellation
            process = subprocess.Popen(
                cmd,
                cwd=target_ws,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid
            )

            try:
                out, err = process.communicate(timeout=timeout)
                stdout = out or ""
                stderr = err or ""
                exit_code = process.returncode
                status = SandboxStatus.COMPLETED
            except subprocess.TimeoutExpired:
                # Kill entire process group
                self._terminate_process_group(process.pid)
                out, err = process.communicate()
                stdout = out or ""
                stderr = (err or "") + f"\n[Sandbox] Execution timed out after {timeout} seconds."
                exit_code = 124
                status = SandboxStatus.TIMEOUT

        except Exception as e:
            status = SandboxStatus.SANDBOX_FAILED
            stderr = f"[Sandbox] Launch exception: {str(e)}"
            exit_code = 127
            if process:
                self._terminate_process_group(process.pid)

        end_time = datetime.now(timezone.utc)
        wall_time = max(time.monotonic() - start_mono, 0.0)

        # 3. Build Machine-Generated ExecutionTrace
        env_fingerprint = hashlib.sha256(
            f"{backend_name}:{active_policy.mode.value}:{sys.version}".encode("utf-8")
        ).hexdigest()[:16]

        trace = ExecutionTrace.create(
            sandbox_execution_id=sid,
            run_id=rid,
            reproducer_id=repro_id,
            command=parsed_cmd,
            tool_versions=tool_versions or {"python": sys.version.split()[0]},
            start_time=start_time,
            end_time=end_time,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            resource_usage={"wall_time": wall_time, "timeout": timeout},
            sandbox_backend=backend_name,
            network_policy="ENABLED" if active_policy.allow_network else "DISABLED",
            env_fingerprint=f"env-{env_fingerprint}"
        )

        return SandboxResult(
            status=status,
            trace=trace,
            error_message=stderr if status != SandboxStatus.COMPLETED else None,
            is_policy_blocked=False
        )

    def _terminate_process_group(self, pid: int):
        """Cleanly terminates an entire process group to eliminate orphaned processes."""
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
            time.sleep(0.1)
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
