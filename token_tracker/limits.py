"""
LLMorch Token Limit Enforcement (Phase 9.1)
Authoritative budget boundary check for tasks, agents, and runs.
Prevents silent execution past configured token limits.
"""

from typing import Dict, Any, Optional
from enum import Enum
from schemas.token import TokenLimitStatus, TokenBudgetConfig


class EnforcementDecision(str, Enum):
    PROCEED = "PROCEED"
    WARN_LOW = "WARN_LOW"
    WARN_NEAR_LIMIT = "WARN_NEAR_LIMIT"
    PAUSE_TASK = "PAUSE_TASK"
    SWITCH_AGENT = "SWITCH_AGENT"
    SWITCH_MODEL = "SWITCH_MODEL"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"
    BLOCK_EXECUTION = "BLOCK_EXECUTION"


class TokenLimitEnforcer:
    """
    Scheduler-level enforcer for token budgets.
    Inspects current usage against task, agent, and run limits.
    """

    def __init__(self, config: Optional[TokenBudgetConfig] = None):
        self.config = config or TokenBudgetConfig()

    def evaluate_status(self, budget: int, consumed: int) -> TokenLimitStatus:
        if budget <= 0:
            return TokenLimitStatus.EXHAUSTED
        remaining = budget - consumed
        if remaining <= 0:
            return TokenLimitStatus.EXHAUSTED
        pct = (remaining / budget) * 100.0
        if pct <= self.config.near_limit_threshold_percent:
            return TokenLimitStatus.NEAR_LIMIT
        if pct <= self.config.low_threshold_percent:
            return TokenLimitStatus.LOW
        return TokenLimitStatus.AVAILABLE

    def check_task_dispatch(
        self,
        task_id: str,
        task_budget: int,
        task_consumed: int,
        run_budget: int,
        run_consumed: int,
        agent_id: Optional[str] = None,
        agent_budget: Optional[int] = None,
        agent_consumed: int = 0,
        estimated_next_cost: int = 0
    ) -> Dict[str, Any]:
        """
        Authoritative check performed before task execution begins or continues.
        Returns enforcement decision and status.
        """
        # 1. Check Global Run Budget
        if (run_budget - run_consumed) <= 0 or (run_budget - (run_consumed + estimated_next_cost)) < 0:
            return {
                "decision": EnforcementDecision.BLOCK_EXECUTION if self.config.action_on_exhausted == "fail" else EnforcementDecision.PAUSE_TASK,
                "status": TokenLimitStatus.EXHAUSTED,
                "scope": "run",
                "remaining": max(0, run_budget - run_consumed),
                "reason": f"Run budget exhausted ({run_consumed}/{run_budget} tokens consumed).",
                "can_proceed": False
            }

        # 2. Check Agent Budget
        if agent_budget and agent_budget > 0:
            agent_rem = agent_budget - agent_consumed
            if agent_rem <= 0 or (agent_rem - estimated_next_cost) < 0:
                return {
                    "decision": EnforcementDecision.SWITCH_AGENT,
                    "status": TokenLimitStatus.EXHAUSTED,
                    "scope": "agent",
                    "remaining": max(0, agent_rem),
                    "reason": f"Agent '{agent_id}' budget exhausted ({agent_consumed}/{agent_budget} consumed). Switch recommended.",
                    "can_proceed": False
                }

        # 3. Check Task Budget
        if task_budget and task_budget > 0:
            task_rem = task_budget - task_consumed
            if task_rem <= 0 or (task_rem - estimated_next_cost) < 0:
                return {
                    "decision": EnforcementDecision.PAUSE_TASK if self.config.action_on_exhausted == "pause" else EnforcementDecision.REQUEST_APPROVAL,
                    "status": TokenLimitStatus.EXHAUSTED,
                    "scope": "task",
                    "remaining": max(0, task_rem),
                    "reason": f"Task '{task_id}' budget exhausted ({task_consumed}/{task_budget} consumed).",
                    "can_proceed": False
                }

        # 4. Check Warning Thresholds on Run
        run_status = self.evaluate_status(run_budget, run_consumed)
        if run_status == TokenLimitStatus.NEAR_LIMIT:
            return {
                "decision": EnforcementDecision.WARN_NEAR_LIMIT,
                "status": TokenLimitStatus.NEAR_LIMIT,
                "scope": "run",
                "remaining": run_budget - run_consumed,
                "reason": "Run token budget near limit (< 10% remaining).",
                "can_proceed": True
            }
        if run_status == TokenLimitStatus.LOW:
            return {
                "decision": EnforcementDecision.WARN_LOW,
                "status": TokenLimitStatus.LOW,
                "scope": "run",
                "remaining": run_budget - run_consumed,
                "reason": "Run token budget low (< 30% remaining).",
                "can_proceed": True
            }

        return {
            "decision": EnforcementDecision.PROCEED,
            "status": TokenLimitStatus.AVAILABLE,
            "scope": "all",
            "remaining": run_budget - run_consumed,
            "reason": "Token budget available.",
            "can_proceed": True
        }
