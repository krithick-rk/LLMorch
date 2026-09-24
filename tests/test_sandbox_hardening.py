"""
Phase 8 Pre-Flight Checkpoint 1: Sandbox Hardening Verification Suite
Tests rootless container isolation (Bubblewrap), network disablement, credential isolation,
read-only root enforcement, resource timeouts, process-group cancellation, and malicious attack fixture blocking.
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sandbox.runner import SandboxRunner
from schemas.sandbox import SandboxMode, SandboxStatus, SandboxPolicy, ExecutionTrace


def test_sandbox_launch_and_basic_execution():
    """Verifies that the rootless sandbox launches and executes a clean command."""
    runner = SandboxRunner()
    with tempfile.TemporaryDirectory() as ws:
        res = runner.execute(
            command=["python3", "-c", "print('sandbox_active')"],
            workspace_dir=ws,
            sandbox_execution_id="sexec-01",
            run_id="run-01",
            reproducer_id="repro-01"
        )
        assert res.status == SandboxStatus.COMPLETED
        assert res.trace is not None
        assert "sandbox_active" in res.trace.stdout
        assert res.trace.exit_code == 0
        assert res.trace.sandbox_backend in ("bubblewrap", "process_group")


def test_sandbox_network_disabled_by_default():
    """Verifies that network egress is strictly disabled by default."""
    runner = SandboxRunner(policy=SandboxPolicy(allow_network=False))
    with tempfile.TemporaryDirectory() as ws:
        script = (
            "import socket\n"
            "try:\n"
            "    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "    s.settimeout(1.0)\n"
            "    s.connect(('1.1.1.1', 80))\n"
            "    print('CONNECTED')\n"
            "except Exception as e:\n"
            "    print('BLOCKED_NETWORK:' + type(e).__name__)\n"
        )
        res = runner.execute(
            command=["python3", "-c", script],
            workspace_dir=ws,
            sandbox_execution_id="sexec-net",
            run_id="run-net",
            reproducer_id="repro-net"
        )
        assert res.status == SandboxStatus.COMPLETED
        assert "BLOCKED_NETWORK" in res.trace.stdout
        assert "CONNECTED" not in res.trace.stdout


def test_sandbox_host_credentials_and_secrets_unavailable():
    """Verifies host credentials (~/.ssh, ~/.aws, ~/.config, tokens) are completely hidden."""
    runner = SandboxRunner()
    with tempfile.TemporaryDirectory() as ws:
        script = (
            "import os\n"
            "prefix = '/home/hackdac/'\n"
            "secrets = [\n"
            "    prefix + '.' + 'ssh',\n"
            "    prefix + '.' + 'aws',\n"
            "    prefix + '.' + 'config',\n"
            "    prefix + '.' + 'claude.json',\n"
            "    prefix + '.' + 'antigravity'\n"
            "]\n"
            "found = [p for p in secrets if os.path.exists(p)]\n"
            "print('ACCESSIBLE_SECRETS:' + str(found))\n"
        )
        res = runner.execute(
            command=["python3", "-c", script],
            workspace_dir=ws,
            sandbox_execution_id="sexec-sec",
            run_id="run-sec",
            reproducer_id="repro-sec"
        )
        assert res.status == SandboxStatus.COMPLETED
        assert "ACCESSIBLE_SECRETS:[]" in res.trace.stdout


def test_sandbox_read_only_root_filesystem():
    """Verifies that the root filesystem is read-only and write attempts are blocked."""
    runner = SandboxRunner()
    with tempfile.TemporaryDirectory() as ws:
        script = (
            "try:\n"
            "    with open('/usr/bin/evil_test_file', 'w') as f:\n"
            "        f.write('bad')\n"
            "    print('WRITE_SUCCEEDED')\n"
            "except Exception as e:\n"
            "    print('WRITE_BLOCKED:' + type(e).__name__)\n"
        )
        res = runner.execute(
            command=["python3", "-c", script],
            workspace_dir=ws,
            sandbox_execution_id="sexec-ro",
            run_id="run-ro",
            reproducer_id="repro-ro"
        )
        assert res.status == SandboxStatus.COMPLETED
        assert "WRITE_BLOCKED" in res.trace.stdout
        assert "WRITE_SUCCEEDED" not in res.trace.stdout


def test_sandbox_writable_scope_constrained_to_workspace():
    """Verifies that writing is allowed ONLY inside the designated workspace."""
    runner = SandboxRunner()
    with tempfile.TemporaryDirectory() as ws:
        script = (
            "import os\n"
            "ws_path = os.getcwd()\n"
            "test_file = os.path.join(ws_path, 'allowed_artifact.txt')\n"
            "with open(test_file, 'w') as f:\n"
            "    f.write('valid_output')\n"
            "print('WORKSPACE_WRITE_OK:' + str(os.path.exists(test_file)))\n"
        )
        res = runner.execute(
            command=["python3", "-c", script],
            workspace_dir=ws,
            sandbox_execution_id="sexec-ws",
            run_id="run-ws",
            reproducer_id="repro-ws"
        )
        assert res.status == SandboxStatus.COMPLETED
        assert "WORKSPACE_WRITE_OK:True" in res.trace.stdout
        assert os.path.exists(os.path.join(ws, "allowed_artifact.txt"))


def test_sandbox_timeout_and_process_cleanup():
    """Verifies execution timeout kills process groups without hanging."""
    # Policy with 2 second timeout
    runner = SandboxRunner(policy=SandboxPolicy(cpu_timeout_seconds=2))
    with tempfile.TemporaryDirectory() as ws:
        # Script that attempts to sleep for 30 seconds
        script = "import time\ntime.sleep(30)\nprint('SLEEP_FINISHED')\n"
        res = runner.execute(
            command=["python3", "-c", script],
            workspace_dir=ws,
            sandbox_execution_id="sexec-to",
            run_id="run-to",
            reproducer_id="repro-to"
        )
        assert res.status == SandboxStatus.TIMEOUT
        assert res.trace.exit_code == 124
        assert "timed out" in res.trace.stderr.lower()


def test_malicious_fixture_policy_blocked():
    """
    Malicious fixture check:
    Attempts explicit path traversal to host secrets -> blocked before execution.
    """
    runner = SandboxRunner()
    with tempfile.TemporaryDirectory() as ws:
        # Command attempting explicit traversal to forbidden path
        cmd = ["cat", "../../../home/hackdac/.ssh/id_rsa"]
        res = runner.execute(
            command=cmd,
            workspace_dir=ws,
            sandbox_execution_id="sexec-bad",
            run_id="run-bad",
            reproducer_id="repro-bad"
        )
        assert res.status == SandboxStatus.POLICY_BLOCKED
        assert res.is_policy_blocked is True
        assert "Policy violation" in res.error_message


def test_execution_trace_evidence_integrity():
    """Verifies that the generated ExecutionTrace contains complete provenance and hashes."""
    runner = SandboxRunner()
    with tempfile.TemporaryDirectory() as ws:
        res = runner.execute(
            command=["python3", "-c", "import sys; sys.stdout.write('evidence_out'); sys.stderr.write('evidence_err')"],
            workspace_dir=ws,
            sandbox_execution_id="sexec-ev",
            run_id="run-ev",
            reproducer_id="repro-ev"
        )
        assert res.status == SandboxStatus.COMPLETED
        trace = res.trace
        assert trace is not None
        assert trace.stdout == "evidence_out"
        assert trace.stderr == "evidence_err"
        assert len(trace.stdout_hash) == 64
        assert len(trace.stderr_hash) == 64
        assert trace.sandbox_backend in ("bubblewrap", "process_group")
        assert trace.network_policy == "DISABLED"
        assert trace.environment_fingerprint.startswith("env-")
