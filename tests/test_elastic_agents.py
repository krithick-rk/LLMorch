"""
Post-Audit Verification Suite: Elastic 1-4 Agent Architecture
Validates dynamic agent discovery, registry health/quota filtering, adaptive strategy engine,
graceful degradation (4 -> 3 -> 2 -> 1 -> 0), failover recovery chains, loop prevention,
capability matching, and provider independence.
"""

import os
import sys
import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Generator, Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters.base import BaseAgentAdapter
from adapters.agy_adapter import AGYAdapter
from adapters.claude_adapter import ClaudeAdapter
from adapters.codex_adapter import CodexAdapter

from schemas.task import Task, TaskStatus, RiskLevel
from schemas.run import Run, RunStatus
from schemas.agent import Agent, AgentInterface
from schemas.health import AgentHealthState, AgentQuotaStatus
from schemas.strategy import StrategyDecision, AgentAssignment
from schemas.errors import ErrorCode
from schemas.event import Event, EventType
from schemas.artifact import Artifact
from schemas.task_result import TaskResult

from registry.agent_registry import AgentRegistry
from orchestrator.strategy import StrategyEngine
from orchestrator.investigation import InvestigationWorkflow
from scheduler.failover import FailoverEngine
from history.database import DatabaseService
from sandbox.workspace import WorkspaceManager


class ControlledMockAdapter(BaseAgentAdapter):
    """
    Controlled Mock Adapter for 4th-agent capacity validation and simulated failure testing.
    Validates architectural elasticity up to 4 agents without requiring a 4th external subscription.
    """
    def __init__(
        self,
        agent_id: str = "agent-mock-04",
        provider: str = "controlled-test-mock",
        health_state: AgentHealthState = AgentHealthState.AVAILABLE,
        capabilities_list: Optional[List[str]] = None,
        should_succeed: bool = True
    ):
        self.agent_id = agent_id
        self.provider = provider
        self._health = health_state
        self._caps = capabilities_list or [
            "repository_analysis", "code_analysis", "rtl_analysis",
            "software_analysis", "debugging", "shell_execution",
            "test_generation", "reproducer_generation", "static_analysis",
            "documentation_analysis", "security_review"
        ]
        self.should_succeed = should_succeed
        self.active_runs: Dict[str, Run] = {}

    def start(self, task: Task) -> Run:
        run = Run(
            task_id=task.task_id,
            agent_id=self.agent_id,
            adapter_version=self.version(),
            workspace_id=task.workspace_policy.allowed_paths[0] if task.workspace_policy.allowed_paths else "ws-mock",
            environment_fingerprint="env-mock-4th-agent",
            status=RunStatus.RUNNING,
            start_time=datetime.now(timezone.utc)
        )
        self.active_runs[run.run_id] = run
        return run

    def execute_task_sync(self, task: Task, workspace_dir: str, context_prompt: str) -> Dict[str, Any]:
        run = self.start(task)
        if self.should_succeed:
            run.status = RunStatus.SUCCEEDED
            run.exit_status = 0
            stdout = json.dumps({
                "hypothesis": f"Fourth-agent controlled hypothesis for {task.objective}",
                "affected_locations": [{"file_path": "schemas/agent.py", "start_line": 1, "end_line": 20}],
                "confidence": 0.88
            })
            exit_code = 0
        else:
            run.status = RunStatus.FAILED
            run.exit_status = 1
            stdout = json.dumps({"error": "Simulated adapter process failure"})
            exit_code = 1
        run.end_time = datetime.now(timezone.utc)
        return {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": "",
            "process_id": 8888,
            "run": run
        }

    def stream(self, run_id: str) -> Generator[Event, None, None]:
        yield Event(run_id=run_id, event_type=EventType.AGENT_DISCOVERY_STARTED, actor=self.agent_id)

    def cancel(self, task_id: str) -> bool:
        return True

    def health(self) -> AgentHealthState:
        return self._health

    def capabilities(self) -> List[str]:
        return list(self._caps)

    def collect_artifacts(self, run_id: str) -> List[Artifact]:
        return []

    def normalize_result(self, raw_output: Any) -> TaskResult:
        if isinstance(raw_output, dict):
            data = raw_output
        else:
            try:
                data = json.loads(str(raw_output))
            except Exception:
                data = {"hypothesis": str(raw_output), "affected_locations": []}
        return TaskResult(
            task_id="t-mock",
            run_id="r-mock",
            status="SUCCEEDED" if self.should_succeed else "FAILED",
            hypothesis=data.get("hypothesis", "Mock hypothesis"),
            affected_locations=data.get("affected_locations", [])
        )

    def version(self) -> str:
        return "1.0.0-controlled-mock"

    def configuration(self) -> Dict[str, Any]:
        return {"controlled_mock": True}

    def workspace_requirements(self) -> Dict[str, Any]:
        return {"isolated": True}


# =====================================================================
# 1. ELASTIC DECISION MATRIX TESTS (CASES A, B, C, D)
# =====================================================================

def test_elastic_case_a_single_agent():
    """Case A: Eligible pool = 1 (AGY) -> system operates with exactly 1 agent."""
    db = DatabaseService(":memory:")
    custom = {"agent-agy-01": AGYAdapter()}
    wf = InvestigationWorkflow(
        repo_path=str(PROJECT_ROOT),
        target_component="schemas",
        db_service=db,
        custom_adapters=custom
    )
    res = wf.run()
    assert res["task_status"] == "READY_FOR_REVIEW"
    assert res["chosen_agent_count"] == 1
    assert len(res["selected_agents"]) == 1
    assert res["selected_agents"][0] == "agent-agy-01"
    assert len(res["child_runs"]) == 1


def test_elastic_case_b_two_agents():
    """Case B: Eligible pool = 2 (AGY + Claude) -> system operates with 2 agents."""
    db = DatabaseService(":memory:")
    custom = {
        "agent-agy-01": AGYAdapter(),
        "agent-claude-01": ClaudeAdapter(),
    }
    wf = InvestigationWorkflow(
        repo_path=str(PROJECT_ROOT),
        target_component="schemas",
        db_service=db,
        custom_adapters=custom
    )
    res = wf.run()
    assert res["task_status"] == "READY_FOR_REVIEW"
    assert res["chosen_agent_count"] <= 2
    assert len(res["selected_agents"]) <= 2
    assert all(a in ["agent-agy-01", "agent-claude-01"] for a in res["selected_agents"])


def test_elastic_case_c_three_agents():
    """Case C: Eligible pool = 3 (AGY + Claude + Codex) -> full production pool operates with 3 agents."""
    db = DatabaseService(":memory:")
    custom = {
        "agent-agy-01": AGYAdapter(),
        "agent-claude-01": ClaudeAdapter(),
        "agent-codex-01": CodexAdapter(),
    }
    wf = InvestigationWorkflow(
        repo_path=str(PROJECT_ROOT),
        target_component="schemas",
        db_service=db,
        custom_adapters=custom,
        requested_agent_count=3
    )
    res = wf.run()
    assert res["task_status"] == "READY_FOR_REVIEW"
    assert res["chosen_agent_count"] == 3
    assert len(res["selected_agents"]) == 3
    assert set(res["selected_agents"]) == {"agent-agy-01", "agent-claude-01", "agent-codex-01"}
    assert len(res["child_runs"]) == 3


def test_elastic_case_d_four_agents_controlled_mock():
    """
    Case D: Eligible pool = 4 (AGY + Claude + Codex + ControlledMockAdapter).
    Proves architecture supports 4 agents without claiming a 4th external provider exists.
    """
    db = DatabaseService(":memory:")
    custom = {
        "agent-agy-01": AGYAdapter(),
        "agent-claude-01": ClaudeAdapter(),
        "agent-codex-01": CodexAdapter(),
        "agent-mock-04": ControlledMockAdapter(agent_id="agent-mock-04"),
    }
    wf = InvestigationWorkflow(
        repo_path=str(PROJECT_ROOT),
        target_component="schemas",
        db_service=db,
        custom_adapters=custom,
        requested_agent_count=4
    )
    res = wf.run()
    assert res["task_status"] == "READY_FOR_REVIEW"
    assert res["chosen_agent_count"] == 4
    assert len(res["selected_agents"]) == 4
    assert "agent-mock-04" in res["selected_agents"]
    assert len(res["child_runs"]) == 4


# =====================================================================
# 2. DYNAMIC DEGRADATION TESTS (4 -> 3 -> 2 -> 1 -> 0)
# =====================================================================

def test_dynamic_degradation_chain_3_to_2_to_1_to_0():
    """
    Validates dynamic degradation when agents drop out one by one.
    When 0 eligible agents remain, system enters an explicit BLOCKED state.
    """
    db = DatabaseService(":memory:")
    registry = AgentRegistry()

    # Register 3 primary agents
    a1 = Agent(agent_id="agent-agy-01", provider="antigravity", capabilities=["repository_analysis", "security_review"], health=AgentHealthState.AVAILABLE, availability=True)
    a2 = Agent(agent_id="agent-claude-01", provider="anthropic", capabilities=["repository_analysis", "security_review"], health=AgentHealthState.AVAILABLE, availability=True)
    a3 = Agent(agent_id="agent-codex-01", provider="openai", capabilities=["repository_analysis", "security_review"], health=AgentHealthState.AVAILABLE, availability=True)
    for a in [a1, a2, a3]:
        registry.register_agent(a)

    engine = StrategyEngine(registry, config={"max_agents": 4})
    task = Task(objective="Critical security investigation across crypto boot tokens", required_capabilities=["repository_analysis", "security_review"])
    scoped_paths = [f"src/file_{i}.c" for i in range(12)]

    # 1. 3 agents available -> selects 3
    dec, _ = engine.evaluate(task, scoped_paths, precheck_count=2)
    assert dec.chosen_agent_count == 3

    # 2. Codex becomes UNAVAILABLE -> 2 eligible -> selects 2
    registry.update_health("agent-codex-01", AgentHealthState.UNAVAILABLE)
    dec, _ = engine.evaluate(task, scoped_paths, precheck_count=2)
    assert dec.chosen_agent_count == 2
    assert "agent-codex-01" not in dec.selected_agents

    # 3. Claude becomes UNAVAILABLE -> 1 eligible -> selects 1
    registry.update_health("agent-claude-01", AgentHealthState.UNAVAILABLE)
    dec, _ = engine.evaluate(task, scoped_paths, precheck_count=2)
    assert dec.chosen_agent_count == 1
    assert dec.selected_agents == ["agent-agy-01"]

    # 4. AGY becomes UNAVAILABLE -> 0 eligible -> selects 0
    registry.update_health("agent-agy-01", AgentHealthState.UNAVAILABLE)
    dec, assignments = engine.evaluate(task, scoped_paths, precheck_count=2)
    assert dec.chosen_agent_count == 0
    assert len(assignments) == 0

    # 5. End-to-end workflow verification with 0 available agents
    wf = InvestigationWorkflow(
        repo_path=str(PROJECT_ROOT),
        target_component="schemas",
        preferred_agent_ids=["agent-agy-01"],
        db_service=db,
        custom_adapters={"agent-agy-01": ControlledMockAdapter(health_state=AgentHealthState.UNAVAILABLE)}
    )
    # Mark agent unavailable in workflow registry
    wf.registry.update_health("agent-agy-01", AgentHealthState.UNAVAILABLE)
    res = wf.run()
    assert res["error"] == "INSUFFICIENT_AGENT_CAPACITY"
    assert res["task_status"] == TaskStatus.BLOCKED.value


# =====================================================================
# 3. FAILOVER & LINEAGE TESTS
# =====================================================================

def test_failover_lineage_and_checkpoint():
    """
    Tests failover sequence from Run 1 to Run 2:
    - Checkpoint created and persisted
    - Replacement candidate selected
    - Run 2 links parent_run_id == Run 1
    - Workspace isolation preserved
    """
    db = DatabaseService(":memory:")
    reg = AgentRegistry()
    wm = WorkspaceManager()

    # Register AGY, Claude, Codex
    reg.register_agent(Agent(agent_id="agent-agy-01", provider="antigravity", capabilities=["security_review"], health=AgentHealthState.AVAILABLE))
    reg.register_agent(Agent(agent_id="agent-claude-01", provider="anthropic", capabilities=["security_review"], health=AgentHealthState.AVAILABLE))
    reg.register_agent(Agent(agent_id="agent-codex-01", provider="openai", capabilities=["security_review"], health=AgentHealthState.AVAILABLE))

    failover = FailoverEngine(db, reg, wm)

    # Create root task and initial failed run
    task = Task(objective="Investigate memory bug", required_capabilities=["security_review"], assigned_agent_id="agent-agy-01")
    failover.task_repo.save(task)

    run_1 = Run(task_id=task.task_id, agent_id="agent-agy-01", status=RunStatus.RUNNING, workspace_id="ws-r1", environment_fingerprint="env1")
    failover.run_repo.save(run_1)

    # AGY crashes
    recovery = failover.handle_failure_and_recover(
        task_id=task.task_id,
        failed_run_id=run_1.run_id,
        error_code=ErrorCode.AGENT_PROCESS_FAILURE,
        failure_reason="Process SIGSEGV crash",
        execution_context={"repo_path": str(PROJECT_ROOT)}
    )

    assert recovery["status"] == "RESUMED"
    assert recovery["failed_run_id"] == run_1.run_id
    assert recovery["replacement_agent_id"] == "agent-claude-01"

    # Verify Run 2 lineage
    run_2 = failover.run_repo.get(recovery["replacement_run_id"])
    assert run_2.parent_run_id == run_1.run_id
    assert run_2.agent_id == "agent-claude-01"
    assert run_2.workspace_id != run_1.workspace_id

    # Verify Checkpoint
    chk = failover.chk_repo.get(recovery["checkpoint_id"])
    assert chk.task_id == task.task_id
    assert chk.recovery_context["failed_agent_id"] == "agent-agy-01"


def test_failure_chain_until_exhaustion():
    """
    Tests failure chain:
    AGY fails -> Claude fails -> Codex fails -> RECOVERY_EXHAUSTED / BLOCKED.
    Verifies that system never reports success merely because all agents failed.
    """
    db = DatabaseService(":memory:")
    reg = AgentRegistry()
    wm = WorkspaceManager()

    reg.register_agent(Agent(agent_id="agent-agy-01", provider="antigravity", capabilities=["sec"], health=AgentHealthState.AVAILABLE))
    reg.register_agent(Agent(agent_id="agent-claude-01", provider="anthropic", capabilities=["sec"], health=AgentHealthState.AVAILABLE))
    reg.register_agent(Agent(agent_id="agent-codex-01", provider="openai", capabilities=["sec"], health=AgentHealthState.AVAILABLE))

    failover = FailoverEngine(db, reg, wm, max_retries_per_task=3)

    task = Task(objective="Deep analysis", required_capabilities=["sec"], assigned_agent_id="agent-agy-01")
    failover.task_repo.save(task)

    # 1. AGY fails
    r1 = Run(task_id=task.task_id, agent_id="agent-agy-01", status=RunStatus.RUNNING, workspace_id="ws-r1", environment_fingerprint="env1")
    failover.run_repo.save(r1)
    res1 = failover.handle_failure_and_recover(task.task_id, r1.run_id, ErrorCode.AGENT_TIMEOUT, "Timeout")
    assert res1["status"] == "RESUMED"
    assert res1["replacement_agent_id"] == "agent-claude-01"

    # 2. Claude fails
    r2 = failover.run_repo.get(res1["replacement_run_id"])
    res2 = failover.handle_failure_and_recover(task.task_id, r2.run_id, ErrorCode.AGENT_PROCESS_FAILURE, "Crash")
    assert res2["status"] == "RESUMED"
    assert res2["replacement_agent_id"] == "agent-codex-01"

    # 3. Codex fails
    r3 = failover.run_repo.get(res2["replacement_run_id"])
    res3 = failover.handle_failure_and_recover(task.task_id, r3.run_id, ErrorCode.QUOTA_EXHAUSTED, "Quota exhausted")
    # All 3 primary agents have failed, no eligible replacements left
    assert res3["status"] in ("RECOVERY_BLOCKED", "RECOVERY_EXHAUSTED")
    updated_task = failover.task_repo.get(task.task_id)
    assert updated_task.status in (TaskStatus.BLOCKED, TaskStatus.FAILED)


def test_failover_loop_prevention():
    """
    Verifies that a cycle: Agent A -> Agent B -> Agent A is impossible.
    Failed agents in the run chain are excluded from future replacement selection.
    """
    db = DatabaseService(":memory:")
    reg = AgentRegistry()
    wm = WorkspaceManager()

    reg.register_agent(Agent(agent_id="agent-a", provider="p1", capabilities=["sec"], health=AgentHealthState.AVAILABLE))
    reg.register_agent(Agent(agent_id="agent-b", provider="p2", capabilities=["sec"], health=AgentHealthState.AVAILABLE))

    failover = FailoverEngine(db, reg, wm)
    task = Task(objective="Loop prevention check", required_capabilities=["sec"], assigned_agent_id="agent-a")
    failover.task_repo.save(task)

    # Run 1: Agent A fails
    r1 = Run(task_id=task.task_id, agent_id="agent-a", status=RunStatus.RUNNING, workspace_id="ws-r1", environment_fingerprint="env1")
    failover.run_repo.save(r1)
    res1 = failover.handle_failure_and_recover(task.task_id, r1.run_id, ErrorCode.AGENT_TIMEOUT, "Timeout")
    assert res1["replacement_agent_id"] == "agent-b"

    # Run 2: Agent B fails -> Agent A must NOT be selected again
    r2 = failover.run_repo.get(res1["replacement_run_id"])
    res2 = failover.handle_failure_and_recover(task.task_id, r2.run_id, ErrorCode.AGENT_TIMEOUT, "Timeout")
    assert res2["status"] == "RECOVERY_BLOCKED"
    assert res2["error"] == "NO_ELIGIBLE_REPLACEMENT"


# =====================================================================
# 4. CAPABILITY MATCHING & QUOTA FILTERING
# =====================================================================

def test_capability_aware_agent_selection():
    """
    Verifies strategy engine respects capability requirements:
    Only agents matching required capabilities are eligible.
    """
    reg = AgentRegistry()
    reg.register_agent(Agent(agent_id="agent-rtl", provider="p1", capabilities=["rtl_analysis", "formal_verification"], health=AgentHealthState.AVAILABLE))
    reg.register_agent(Agent(agent_id="agent-sw", provider="p2", capabilities=["software_analysis", "security_review"], health=AgentHealthState.AVAILABLE))

    engine = StrategyEngine(reg, config={"max_agents": 4})
    task_rtl = Task(objective="RTL property verification", required_capabilities=["rtl_analysis", "formal_verification"])

    dec, assignments = engine.evaluate(task_rtl, scoped_paths=["hw/top.sv"], precheck_count=1)
    assert dec.chosen_agent_count == 1
    assert dec.selected_agents == ["agent-rtl"]
    assert any("agent-sw" in exc for exc in dec.excluded_agents)


def test_quota_limited_agent_exclusion():
    """
    Verifies agents with exhausted quota or QUOTA_LIMITED health are excluded from dispatch.
    """
    reg = AgentRegistry()
    reg.register_agent(Agent(agent_id="agent-ok", provider="p1", capabilities=["sec"], health=AgentHealthState.AVAILABLE))
    reg.register_agent(Agent(agent_id="agent-quota-exhausted", provider="p2", capabilities=["sec"], health=AgentHealthState.QUOTA_LIMITED, quota_status=AgentQuotaStatus.EXHAUSTED))

    engine = StrategyEngine(reg, config={"max_agents": 4})
    task = Task(objective="Test task", required_capabilities=["sec"])

    dec, assignments = engine.evaluate(task, scoped_paths=["test.c"], precheck_count=0)
    assert dec.selected_agents == ["agent-ok"]
    assert "agent-quota-exhausted" not in dec.selected_agents
    assert any("agent-quota-exhausted" in exc for exc in dec.excluded_agents)


def test_budget_constraints_selection():
    """
    Verifies low budget restricts agent count to 1 even for complex tasks with 4 eligible agents.
    """
    reg = AgentRegistry()
    for i in range(4):
        reg.register_agent(Agent(agent_id=f"agent-{i+1}", provider="test", capabilities=["sec"], health=AgentHealthState.AVAILABLE))

    engine = StrategyEngine(reg, config={"max_agents": 4})
    task = Task(objective="Critical security investigation across tokens", required_capabilities=["sec"])
    scoped_paths = [f"src/file_{i}.c" for i in range(12)]

    # Budget < 15.0 forces single agent
    dec, assignments = engine.evaluate(task, scoped_paths, precheck_count=2, budget_available=10.0)
    assert dec.chosen_agent_count == 1
    assert any("budget constrained" in r.lower() for r in dec.reason)


# =====================================================================
# 5. REAL AGENT COMBINATION TESTS (AGY, Claude, Codex)
# =====================================================================

def test_real_agent_combinations_pair_and_solo():
    """
    Cross-tests the 3 production agents in solo and paired combinations:
    - AGY solo
    - Claude solo
    - Codex solo
    - AGY + Claude
    - AGY + Codex
    - Claude + Codex
    """
    db = DatabaseService(":memory:")

    # AGY solo
    wf_agy = InvestigationWorkflow(repo_path=str(PROJECT_ROOT), target_component="schemas", preferred_agent_ids=["agent-agy-01"], db_service=db)
    res_agy = wf_agy.run()
    assert res_agy["task_status"] == "READY_FOR_REVIEW"
    assert res_agy["selected_agents"] == ["agent-agy-01"]

    # Claude solo
    wf_claude = InvestigationWorkflow(repo_path=str(PROJECT_ROOT), target_component="schemas", preferred_agent_ids=["agent-claude-01"], db_service=db)
    res_claude = wf_claude.run()
    assert res_claude["task_status"] == "READY_FOR_REVIEW"
    assert res_claude["selected_agents"] == ["agent-claude-01"]

    # Codex solo
    wf_codex = InvestigationWorkflow(repo_path=str(PROJECT_ROOT), target_component="schemas", preferred_agent_ids=["agent-codex-01"], db_service=db)
    res_codex = wf_codex.run()
    assert res_codex["task_status"] == "READY_FOR_REVIEW"
    assert res_codex["selected_agents"] == ["agent-codex-01"]

    # AGY + Claude
    wf_ac = InvestigationWorkflow(repo_path=str(PROJECT_ROOT), target_component="schemas", preferred_agent_ids=["agent-agy-01", "agent-claude-01"], db_service=db)
    res_ac = wf_ac.run()
    assert set(res_ac["selected_agents"]) == {"agent-agy-01", "agent-claude-01"}

    # AGY + Codex
    wf_ax = InvestigationWorkflow(repo_path=str(PROJECT_ROOT), target_component="schemas", preferred_agent_ids=["agent-agy-01", "agent-codex-01"], db_service=db)
    res_ax = wf_ax.run()
    assert set(res_ax["selected_agents"]) == {"agent-agy-01", "agent-codex-01"}

    # Claude + Codex
    wf_cx = InvestigationWorkflow(repo_path=str(PROJECT_ROOT), target_component="schemas", preferred_agent_ids=["agent-claude-01", "agent-codex-01"], db_service=db)
    res_cx = wf_cx.run()
    assert set(res_cx["selected_agents"]) == {"agent-claude-01", "agent-codex-01"}


# =====================================================================
# 6. MATHEMATICAL INVARIANTS & OPENCODE/GEMINI OPTIONALITY
# =====================================================================

def test_elastic_agent_mathematical_invariants():
    """
    Mathematical invariants check:
    0 <= selected_agent_count <= eligible_agent_count
    selected_agent_count <= configured_max_agents <= 4
    selected_agent IDs are unique
    all selected agents are eligible at dispatch time
    """
    reg = AgentRegistry()
    for i in range(4):
        reg.register_agent(Agent(agent_id=f"agent-inv-{i+1}", provider="test", capabilities=["sec"], health=AgentHealthState.AVAILABLE))

    engine = StrategyEngine(reg, config={"max_agents": 4})
    task = Task(objective="Invariant verification", required_capabilities=["sec"])

    for pool_size in [0, 1, 2, 3, 4]:
        subset_ids = [f"agent-inv-{i+1}" for i in range(pool_size)]
        dec, _ = engine.evaluate(task, scoped_paths=["foo.c"], precheck_count=1, preferred_agent_ids=subset_ids)

        assert 0 <= dec.chosen_agent_count <= len(subset_ids)
        assert dec.chosen_agent_count <= 4
        assert len(set(dec.selected_agents)) == len(dec.selected_agents)
        assert set(dec.selected_agents).issubset(set(subset_ids))


def test_opencode_optional_status_does_not_corrupt_pipeline():
    """
    Verifies that OpenCode being placeholder/optional/unavailable does NOT corrupt
    the agent registry, strategy engine, scheduler, or failover pipeline.
    """
    reg = AgentRegistry()
    # Register production primary agents
    reg.register_agent(Agent(agent_id="agent-agy-01", provider="antigravity", capabilities=["sec"], health=AgentHealthState.AVAILABLE))
    reg.register_agent(Agent(agent_id="agent-claude-01", provider="anthropic", capabilities=["sec"], health=AgentHealthState.AVAILABLE))
    # Register OpenCode as optional placeholder / degraded / unavailable
    reg.register_agent(Agent(
        agent_id="agent-opencode-01",
        provider="opencode",
        capabilities=["sec"],
        health=AgentHealthState.UNAVAILABLE,
        availability=False,
        metadata={"role": "optional_secondary"}
    ))

    engine = StrategyEngine(reg, config={"max_agents": 4})
    task = Task(objective="Investigate auth crypto token state transitions", required_capabilities=["sec"])

    dec, assignments = engine.evaluate(task, scoped_paths=["auth.c", "token.c", "crypto.c", "key.c"], precheck_count=1)
    assert "agent-opencode-01" not in dec.selected_agents
    assert any("agent-opencode-01" in exc for exc in dec.excluded_agents)
    assert dec.chosen_agent_count == 2
    assert set(dec.selected_agents) == {"agent-agy-01", "agent-claude-01"}
