"""
Unit & Integration Tests - Phase 3 Two-Agent Independent Parallel Execution
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters.base import BaseAgentAdapter
from adapters.agy_adapter import AGYAdapter
from adapters.claude_adapter import ClaudeAdapter
from adapters.codex_adapter import CodexAdapter
from registry.agent_registry import AgentRegistry
from schemas.agent import Agent, AgentInterface
from schemas.health import AgentHealthState
from schemas.task_result import TaskResult
from schemas.evidence import Evidence, EvidenceSourceType
from correlation.engine import FindingCorrelator, CorrelationType
from orchestrator.investigation import InvestigationWorkflow
from history.database import DatabaseService


def test_adapters_pool_availability():
    agy = AGYAdapter()
    claude = ClaudeAdapter()
    codex = CodexAdapter()

    assert isinstance(agy, BaseAgentAdapter)
    assert isinstance(claude, BaseAgentAdapter)
    assert isinstance(codex, BaseAgentAdapter)


def test_insufficient_agent_capacity_reporting():
    db = DatabaseService(":memory:")
    # Initialize workflow with no available agents in registry
    wf = InvestigationWorkflow(repo_path=str(PROJECT_ROOT), target_component="schemas", preferred_agent_ids=["non-existent-1", "non-existent-2"], db_service=db)
    res = wf.run()
    assert "error" in res
    assert res["error"] == "INSUFFICIENT_AGENT_CAPACITY"


def test_workspace_and_context_isolation_in_parallel():
    db = DatabaseService(":memory:")
    wf = InvestigationWorkflow(
        repo_path=str(PROJECT_ROOT),
        target_component="schemas",
        preferred_agent_ids=["agent-agy-01", "agent-claude-01"],
        db_service=db
    )
    res = wf.run()
    assert res["task_status"] == "READY_FOR_REVIEW"
    assert len(res["child_runs"]) == 2

    ws_a = res["child_runs"][0]["workspace"]
    ws_b = res["child_runs"][1]["workspace"]

    # Verify separate workspaces allocated
    assert ws_a != ws_b
    assert "wf-" in ws_a and "wf-" in ws_b


def test_correlator_classifications():
    res1 = {"agent_id": "agent-agy-01", "run_id": "run-1", "task_result": TaskResult(task_id="t1", run_id="r1", status="SUCCEEDED", hypothesis="Buffer overflow in DMA", affected_locations=[{"file_path": "dma.c"}])}
    res2 = {"agent_id": "agent-claude-01", "run_id": "run-2", "task_result": TaskResult(task_id="t2", run_id="r2", status="SUCCEEDED", hypothesis="Buffer overflow in DMA", affected_locations=[{"file_path": "dma.c"}])}

    ev1 = Evidence(task_id="t1", run_id="r1", agent_id="agent-agy-01", source_type=EvidenceSourceType.TOOL_OUTPUT, raw_hash="h1", canonical_hash="h1", semantic_fingerprint="s1", environment_fingerprint="e1", exit_status=0)

    corr = FindingCorrelator.correlate_results([res1, res2], [ev1])
    assert corr.clusters[0].classification == CorrelationType.DUPLICATE

    res3 = {"agent_id": "agent-claude-01", "run_id": "run-2", "task_result": TaskResult(task_id="t2", run_id="r2", status="SUCCEEDED", hypothesis="No vulnerability found", affected_locations=[{"file_path": "dma.c"}])}
    corr_contradict = FindingCorrelator.correlate_results([res1, res3], [ev1])
    assert corr_contradict.clusters[0].classification == CorrelationType.CONTRADICTORY


def test_end_to_end_parallel_pair_execution_agy_claude():
    db = DatabaseService(":memory:")
    wf = InvestigationWorkflow(
        repo_path=str(PROJECT_ROOT),
        target_component="schemas",
        preferred_agent_ids=["agent-agy-01", "agent-claude-01"],
        db_service=db
    )
    res = wf.run()
    assert res["task_status"] == "READY_FOR_REVIEW"
    assert len(res["selected_agents"]) == 2
    assert "agent-agy-01" in res["selected_agents"]
    assert "agent-claude-01" in res["selected_agents"]
    assert len(res["independent_hypotheses"]) == 2


def test_end_to_end_parallel_pair_execution_agy_codex():
    db = DatabaseService(":memory:")
    wf = InvestigationWorkflow(
        repo_path=str(PROJECT_ROOT),
        target_component="schemas",
        preferred_agent_ids=["agent-agy-01", "agent-codex-01"],
        db_service=db
    )
    res = wf.run()
    assert res["task_status"] == "READY_FOR_REVIEW"
    assert "agent-agy-01" in res["selected_agents"]
    assert "agent-codex-01" in res["selected_agents"]


def test_end_to_end_parallel_pair_execution_claude_codex():
    db = DatabaseService(":memory:")
    wf = InvestigationWorkflow(
        repo_path=str(PROJECT_ROOT),
        target_component="schemas",
        preferred_agent_ids=["agent-claude-01", "agent-codex-01"],
        db_service=db
    )
    res = wf.run()
    assert res["task_status"] == "READY_FOR_REVIEW"
    assert "agent-claude-01" in res["selected_agents"]
    assert "agent-codex-01" in res["selected_agents"]


if __name__ == "__main__":
    pytest.main([__file__])
