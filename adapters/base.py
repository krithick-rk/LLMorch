"""
LLMorch Adapters - Base Provider-Neutral Adapter Contract
"""

from abc import ABC, abstractmethod
from typing import List, Generator, Any, Dict, Optional
from schemas.task import Task
from schemas.run import Run
from schemas.event import Event
from schemas.artifact import Artifact
from schemas.health import AgentHealthState
from schemas.task_result import TaskResult


class BaseAgentAdapter(ABC):
    """
    Provider-neutral interface boundary for agent execution.
    The core orchestrator interacts only through this adapter interface.
    """

    @abstractmethod
    def start(self, task: Task) -> Run:
        """Initiates task execution attempt and returns a Run object."""
        pass

    @abstractmethod
    def execute_task_sync(self, task: Task, workspace_dir: str, context_prompt: str) -> Dict[str, Any]:
        """Launches process synchronously with process supervision and returns outcome dict."""
        pass

    @abstractmethod
    def stream(self, run_id: str) -> Generator[Event, None, None]:
        """Streams real-time execution audit events for the given run_id."""
        pass

    @abstractmethod
    def cancel(self, task_id: str) -> bool:
        """Cancels an active execution attempt for task_id."""
        pass

    @abstractmethod
    def health(self) -> AgentHealthState:
        """Queries operational health status of the adapter/agent."""
        pass

    @abstractmethod
    def capabilities(self) -> List[str]:
        """Returns list of supported capability strings."""
        pass

    @abstractmethod
    def collect_artifacts(self, run_id: str) -> List[Artifact]:
        """Gathers produced artifacts for a completed or failed run."""
        pass

    @abstractmethod
    def normalize_result(self, raw_output: Any) -> TaskResult:
        """Normalizes raw agent CLI/API output into structured TaskResult schema."""
        pass

    @abstractmethod
    def version(self) -> str:
        """Returns version string of the adapter implementation."""
        pass

    @abstractmethod
    def configuration(self) -> Dict[str, Any]:
        """Returns active adapter configuration settings."""
        pass

    @abstractmethod
    def workspace_requirements(self) -> Dict[str, Any]:
        """Returns workspace isolation and mount requirements."""
        pass
