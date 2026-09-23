"""
Unit Tests - Schemas & Data Contracts Validation
"""

import pytest
import sys
from pathlib import Path
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.task import Task, TaskStatus, RiskLevel
from schemas.run import Run, RunStatus
from schemas.agent import Agent, AgentInterface
from schemas.health import AgentHealthState, AgentUsageStatus, AgentQuotaStatus
from schemas.checkpoint import Checkpoint
from schemas.artifact import Artifact, ArtifactType
from schemas.evidence import Evidence, EvidenceSourceType
from schemas.finding import Finding, FindingState, FindingLocation
from schemas.analysis_unit import AnalysisUnit, AnalysisUnitType
from schemas.security_surface import SecuritySurface
from schemas.event import Event, EventType
from schemas.policy import AgentPolicy
from schemas.errors import ErrorCode, LLMorchError


def test_task_schema_validation():
    task = Task(objective="Analyze security surface")
    assert task.schema_version == "1.0.0"
    assert task.status == TaskStatus.QUEUED
    assert task.risk_level == RiskLevel.MEDIUM
    assert task.task_id.startswith("task-")

    # Test serialization / deserialization
    json_data = task.model_dump_json()
    deserialized = Task.model_validate_json(json_data)
    assert deserialized.task_id == task.task_id
    assert deserialized.objective == task.objective


def test_agent_schema_validation():
    agent = Agent(
        agent_id="agent-agy-01",
        provider="antigravity",
        interface=AgentInterface.CLI,
        capabilities=["repository_analysis", "rtl_analysis"]
    )
    assert agent.agent_id == "agent-agy-01"
    assert agent.health == AgentHealthState.AVAILABLE
    assert agent.schema_version == "1.0.0"


def test_health_state_unknown_quota():
    usage = AgentUsageStatus(remaining_quota=None)
    assert usage.remaining_quota is None  # Unknown, never faked


def test_checkpoint_schema():
    chk = Checkpoint(
        task_id="task-123",
        completed_subtasks=["subtask-1"],
        remaining_subtasks=["subtask-2"]
    )
    assert chk.task_id == "task-123"
    assert chk.schema_version == "1.0.0"


def test_finding_schema():
    finding = Finding(
        fingerprint="fp-12345",
        hypothesis="Buffer overflow in DMA controller",
        locations=[FindingLocation(file_path="src/dma.c", start_line=42)]
    )
    assert finding.state == FindingState.HYPOTHESIS
    assert finding.locations[0].file_path == "src/dma.c"


def test_agent_policy_validation():
    policy = AgentPolicy(min_agents=1, max_agents=4)
    assert policy.min_agents == 1
    assert policy.max_agents == 4

    with pytest.raises(ValidationError):
        AgentPolicy(min_agents=3, max_agents=2)


if __name__ == "__main__":
    pytest.main([__file__])
