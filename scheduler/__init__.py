"""
LLMorch Scheduler Package (Phase 9.1)
Provides scheduler contract, FailoverEngine, ModelRouter, and AgentSwitcher.
"""

from schemas.task import Task
from .failover import FailoverEngine
from .model_router import ModelRouter
from .agent_switcher import AgentSwitcher


class BaseScheduler:
    """Task queue and dispatching engine abstraction."""
    def schedule(self, task: Task) -> bool:
        return True


__all__ = ["BaseScheduler", "FailoverEngine", "ModelRouter", "AgentSwitcher"]
