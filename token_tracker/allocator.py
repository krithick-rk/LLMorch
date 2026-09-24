"""
LLMorch Deterministic Token Budget Allocator (Phase 9.1)
Calculates deterministic, auditable budget distributions across agents, tasks, and reserve pools.
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class BudgetAllocationPlan(BaseModel):
    """Auditable budget allocation outcome."""
    run_budget: int
    reserved_budget: int
    available_budget: int
    agent_budgets: Dict[str, int]
    task_budget: int
    allocation_policy: str
    rationale: str


class TokenBudgetAllocator:
    """
    Deterministic budget allocator for LLMorch execution plane.
    Partitions run token ceiling into agent allocations, task budgets, and safety reserves.
    """

    def __init__(self, reserve_percent: float = 20.0):
        self.reserve_percent = reserve_percent

    def allocate(
        self,
        run_budget: int,
        agent_ids: List[str],
        task_priority: str = "MEDIUM",
        task_complexity: str = "medium",
        estimated_task_cost: Optional[int] = None,
        allocation_policy: str = "BALANCED"
    ) -> BudgetAllocationPlan:
        """
        Calculates deterministic budget allocation.
        Reserve is calculated first (default 20%).
        The remaining pool is divided among eligible active agents and task limits.
        """
        if run_budget <= 0:
            raise ValueError("run_budget must be positive")

        num_agents = max(1, len(agent_ids))
        reserved = int(run_budget * (self.reserve_percent / 100.0))
        distributable = run_budget - reserved

        # Complexity multiplier for task budget
        complexity_multipliers = {
            "low": 0.5,
            "medium": 1.0,
            "high": 1.75,
            "critical": 2.5
        }
        comp_mult = complexity_multipliers.get(task_complexity.lower(), 1.0)

        # Priority multiplier
        priority_multipliers = {
            "low": 0.8,
            "medium": 1.0,
            "high": 1.4,
            "critical": 2.0
        }
        prio_mult = priority_multipliers.get(task_priority.lower(), 1.0)

        # Baseline per-agent distribution
        agent_budgets: Dict[str, int] = {}
        if allocation_policy == "BALANCED" or not agent_ids:
            per_agent = int(distributable / num_agents)
            for aid in agent_ids:
                agent_budgets[aid] = per_agent
        elif allocation_policy == "PRIMARY_WEIGHTED":
            # Primary agent gets 50%, rest split the remainder
            primary = agent_ids[0]
            agent_budgets[primary] = int(distributable * 0.5)
            remaining_dist = distributable - agent_budgets[primary]
            other_agents = agent_ids[1:]
            per_other = int(remaining_dist / max(1, len(other_agents)))
            for aid in other_agents:
                agent_budgets[aid] = per_other
        else:
            per_agent = int(distributable / num_agents)
            for aid in agent_ids:
                agent_budgets[aid] = per_agent

        # Task budget calculation
        if estimated_task_cost and estimated_task_cost > 0:
            task_budget = int(min(distributable * 0.4, estimated_task_cost * comp_mult * prio_mult))
        else:
            base_task = distributable / (num_agents * 3)
            task_budget = int(min(distributable * 0.3, base_task * comp_mult * prio_mult))

        task_budget = max(5000, task_budget)

        rationale = (
            f"Allocated run budget {run_budget}: reserved {reserved} ({self.reserve_percent}%), "
            f"distributable {distributable} across {num_agents} agent(s) under policy '{allocation_policy}', "
            f"task budget {task_budget} (complexity: {task_complexity}, priority: {task_priority})."
        )

        return BudgetAllocationPlan(
            run_budget=run_budget,
            reserved_budget=reserved,
            available_budget=distributable,
            agent_budgets=agent_budgets,
            task_budget=task_budget,
            allocation_policy=allocation_policy,
            rationale=rationale
        )
