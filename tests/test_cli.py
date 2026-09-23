"""
Unit Tests - CLI Entrypoints
"""

import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llmorch.cli import run_doctor, run_agents, run_config, run_version


def test_cli_doctor_runs_without_exception(capsys):
    run_doctor()
    captured = capsys.readouterr()
    assert "Doctor Status: ALL PHASE 0 FOUNDATIONAL SYSTEMS OPERATIONAL" in captured.out


def test_cli_agents_runs(capsys):
    run_agents()
    captured = capsys.readouterr()
    assert "agent-agy-01" in captured.out


def test_cli_config_runs(capsys):
    run_config()
    captured = capsys.readouterr()
    assert "LLMorch Active Configuration" in captured.out


def test_cli_version_runs(capsys):
    run_version()
    captured = capsys.readouterr()
    assert "LLMorch version: 0.1.0" in captured.out


if __name__ == "__main__":
    pytest.main([__file__])
