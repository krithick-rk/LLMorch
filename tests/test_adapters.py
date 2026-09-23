"""
Unit Tests - Adapter Abstraction & AGY Adapter
"""

import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters.agy_adapter import AGYAdapter
from schemas.task import Task
from schemas.run import RunStatus
from schemas.health import AgentHealthState


def test_agy_adapter_start_and_cancel():
    adapter = AGYAdapter()
    assert adapter.version() == "1.0.0"
    assert adapter.health() == AgentHealthState.AVAILABLE

    task = Task(objective="Audit RTL design")
    run = adapter.start(task)
    assert run.task_id == task.task_id
    assert run.agent_id == "agent-agy-01"
    assert run.status == RunStatus.RUNNING

    cancelled = adapter.cancel(task.task_id)
    assert cancelled is True


def test_agy_adapter_capabilities():
    adapter = AGYAdapter()
    caps = adapter.capabilities()
    assert "repository_analysis" in caps
    assert "rtl_analysis" in caps
    assert "security_review" in caps


def test_agy_adapter_normalize_result():
    adapter = AGYAdapter()
    res = adapter.normalize_result({"status": "ok", "findings": []})
    assert res["status"] == "ok"
    assert res["findings"] == []


if __name__ == "__main__":
    pytest.main([__file__])
