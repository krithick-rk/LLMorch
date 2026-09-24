"""
LLMorch Adaptive Strategy Engine (Phase 4)
Determines the smallest useful agent pool (1-4 agents) and task-time role assignments based on
deterministic task signals, hard availability/capability constraints, budget, and risk policy.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json

from schemas.task import Task
from schemas.agent import Agent
from schemas.health import AgentHealthState, AgentQuotaStatus
from schemas.strategy import StrategyDecision, AgentAssignment
from registry.agent_registry import AgentRegistry


class StrategyEngine:
    """
    Model-Independent Adaptive Strategy Engine.
    Evaluates task requirements, derives complexity/parallelism/uncertainty signals,
    applies hard constraint filtering, and selects the minimum necessary agent pool.
    """

    SECURITY_KEYWORDS = [
        "crypto", "key", "auth", "privilege", "boot", "entropy",
        "lock", "register", "state", "gate", "rtl", "transition",
        "access", "secret", "token", "session"
    ]

    def __init__(self, registry: AgentRegistry, config: Optional[Dict[str, Any]] = None):
        self.registry = registry
        self.config = config or {}
        self.max_agents_limit = int(self.config.get("max_agents", 4))
        self.min_agents_limit = int(self.config.get("min_agents", 1))

    def extract_signals(self, task: Task, scoped_paths: List[str], precheck_count: int) -> Dict[str, Any]:
        """
        Derives deterministic assessment signals from repository and task data.
        """
        file_count = len(scoped_paths)
        has_security_keyword = any(
            kw in task.objective.lower() or any(kw in p.lower() for p in scoped_paths)
            for kw in self.SECURITY_KEYWORDS
        )

        # Complexity Signal
        if file_count <= 2 and not has_security_keyword:
            complexity = "LOW"
        elif file_count <= 5:
            complexity = "MEDIUM"
        elif file_count <= 15 or has_security_keyword:
            complexity = "HIGH"
        else:
            complexity = "CRITICAL"

        # Security Sensitivity Signal
        security_sensitivity = "HIGH" if has_security_keyword else ("MEDIUM" if file_count > 3 else "LOW")

        # Uncertainty Signal
        uncertainty = "HIGH" if precheck_count > 0 or has_security_keyword else ("MEDIUM" if file_count > 3 else "LOW")

        # Parallelism Signal
        parallelism = "HIGH" if file_count > 5 or (has_security_keyword and file_count > 2) else ("MODERATE" if file_count > 1 else "LOW")

        return {
            "complexity": complexity,
            "security_sensitivity": security_sensitivity,
            "uncertainty": uncertainty,
            "parallelism": parallelism,
            "file_count": file_count,
            "precheck_count": precheck_count,
            "has_security_keyword": has_security_keyword
        }

    def filter_candidates(self, required_capabilities: List[str]) -> Tuple[List[Agent], List[str], List[str]]:
        """
        Applies hard constraints to candidate agents from registry.
        Returns: (eligible_agents, candidate_ids, excluded_ids)
        """
        all_agents = self.registry.list_agents()
        candidate_ids = [a.agent_id for a in all_agents]
        eligible: List[Agent] = []
        excluded: List[str] = []

        for agent in all_agents:
            # Hard Constraint 1: Availability & Health
            if (
                not agent.availability
                or agent.health not in (AgentHealthState.AVAILABLE, AgentHealthState.DEGRADED)
                or getattr(agent, "quota_status", None) == AgentQuotaStatus.EXHAUSTED
            ):
                excluded.append(f"{agent.agent_id} (Health: {agent.health.value}, Avail: {agent.availability})")
                continue

            # Hard Constraint 2: Required Capabilities Match
            missing_caps = [cap for cap in required_capabilities if cap not in agent.capabilities]
            if missing_caps:
                excluded.append(f"{agent.agent_id} (Missing caps: {missing_caps})")
                continue

            eligible.append(agent)

        return eligible, candidate_ids, excluded

    def evaluate(
        self,
        task: Task,
        scoped_paths: List[str],
        precheck_count: int,
        forced_agent_count: Optional[int] = None,
        budget_available: float = 100.0,
        preferred_agent_ids: Optional[List[str]] = None
    ) -> Tuple[StrategyDecision, List[AgentAssignment]]:
        """
        Evaluates task signals and returns an explainable StrategyDecision and AgentAssignment list.
        """
        # 1. Required Capabilities
        required_caps = task.required_capabilities or ["repository_analysis", "security_review"]

        # 2. Hard Constraint Filtering
        eligible_agents, candidate_ids, excluded_ids = self.filter_candidates(required_caps)

        if preferred_agent_ids is not None:
            eligible_agents = [a for a in eligible_agents if a.agent_id in preferred_agent_ids]

        # 3. Extract Signals
        signals = self.extract_signals(task, scoped_paths, precheck_count)
        complexity = signals["complexity"]
        security = signals["security_sensitivity"]
        uncertainty = signals["uncertainty"]
        parallelism = signals["parallelism"]

        # 4. Determine Optimal Target Agent Count (Minimum Useful Pool Rule)
        reasons = []

        if forced_agent_count is not None:
            target_count = forced_agent_count
            reasons.append(f"Explicit CLI/task override requested agent_count={forced_agent_count}")
        elif budget_available < 15.0:
            target_count = 1
            reasons.append("Task budget constrained (< 15 units); restricted to 1 agent")
        elif complexity == "LOW" and security == "LOW":
            target_count = 1
            reasons.append("Low complexity single-component task; 1 agent sufficient")
        elif complexity in ("HIGH", "CRITICAL") and parallelism == "HIGH":
            target_count = 4
            reasons.append("Critical complexity, high parallelism, and multi-domain scope; 4 agents selected")
        elif (complexity == "HIGH" or security == "HIGH" or uncertainty == "HIGH"):
            target_count = 3
            reasons.append("High complexity/security sensitivity with multiple eligible capabilities; 3 agents selected")
        elif security in ("HIGH", "MEDIUM") or uncertainty in ("HIGH", "MEDIUM"):
            target_count = 2
            reasons.append("Moderate/High security sensitivity; 2 independent agents selected for confirmation")
        else:
            target_count = 1
            reasons.append("Standard single-agent scope")

        # 5. Cap by Available Eligible Capacity & System Policy Limit
        chosen_count = min(target_count, len(eligible_agents), self.max_agents_limit)
        chosen_count = max(chosen_count, 0)
        chosen_agents = eligible_agents[:chosen_count]
        chosen_agent_ids = [a.agent_id for a in chosen_agents]

        if target_count > len(eligible_agents):
            reasons.append(f"Requested {target_count} agents, but only {len(eligible_agents)} eligible agents available in registry")

        # 6. Create StrategyDecision Record
        decision = StrategyDecision(
            task_id=task.task_id,
            chosen_agent_count=chosen_count,
            selected_agents=chosen_agent_ids,
            candidate_agents=candidate_ids,
            excluded_agents=excluded_ids,
            required_capabilities=required_caps,
            estimated_complexity=complexity,
            estimated_parallelism=parallelism,
            estimated_uncertainty=uncertainty,
            security_sensitivity=security,
            budget_available=budget_available,
            estimated_cost=float(chosen_count * 1.5),
            reason=reasons,
            expected_benefit=f"Independent research pass across {chosen_count} agent(s)",
            escalation_conditions=["Evidence contradiction between discovery passes", "Unresolved security hypothesis"],
            stop_conditions=["Low marginal benefit", "Max capacity reached", "Budget exhausted"]
        )

        # 7. Create Role Assignments
        roles = ["primary_investigation", "independent_investigation", "architecture_analysis", "adversarial_review"]
        assignments: List[AgentAssignment] = []

        for idx, agent in enumerate(chosen_agents):
            role_name = roles[idx] if idx < len(roles) else f"auxiliary_pass_{idx+1}"
            assignment = AgentAssignment(
                strategy_decision_id=decision.decision_id,
                task_id=task.task_id,
                agent_id=agent.agent_id,
                role=role_name,
                required_capabilities=required_caps,
                assignment_reason=f"Selected for role '{role_name}' based on capability match and rank #{idx+1}"
            )
            assignments.append(assignment)

        return decision, assignments
