"""
LLMorch Scheduler Package (Phase 0 Foundation)
Provides scheduler contract placeholders for task dispatching and queue management.
"""

from schemas.task import Task


class BaseScheduler:
    """Task queue and dispatching engine abstraction."""
    def schedule(self, task: Task) -> bool:
        return True
