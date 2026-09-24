"""
LLMorch Model Router (Phase 9.1)
Authoritative scheduler component for selecting and routing tasks to models.
Resolves AUTO, MANUAL, and POLICY selection modes.
"""

import logging
from typing import Optional, Dict, Any, List
from schemas.model import (
    Model,
    ModelSelectionMode,
    ModelPolicy,
    ModelSelectionRequest,
    ModelSelectionResult,
)
from schemas.task import Task
from registry.model_registry import ModelRegistry
from registry.agent_registry import AgentRegistry

logger = logging.getLogger(__name__)


class ModelRouter:
    """
    Model routing engine at the scheduler/control-plane level.
    Never uses hard-coded provider if/elif statements.
    Resolves policies to configuration metadata and matches explicit capability tags.
    """

    def __init__(self, model_registry: ModelRegistry, agent_registry: Optional[AgentRegistry] = None):
        self.model_registry = model_registry
        self.agent_registry = agent_registry

    def route_task(
        self,
        task: Task,
        agent_id: str,
        mode: ModelSelectionMode = ModelSelectionMode.AUTO,
        policy: Optional[ModelPolicy] = None,
        preferred_model_id: Optional[str] = None,
        remaining_token_budget: Optional[int] = None
    ) -> ModelSelectionResult:
        """
        Determines the optimal model for a given task and agent assignment.
        """
        # Determine language and complexity from task attributes
        lang = None
        task_type = "investigation"
        complexity = "medium"

        if task.risk_level.value in ("CRITICAL", "HIGH"):
            complexity = "high"

        obj_lower = task.objective.lower()
        if "rtl" in obj_lower or "verilog" in obj_lower:
            lang = "systemverilog"
            task_type = "rtl_analysis"
        elif "triage" in obj_lower or "discovery" in obj_lower or "intake" in obj_lower:
            task_type = "fast_triage"
            complexity = "low"
        elif "repro" in obj_lower or "sandbox" in obj_lower:
            task_type = "reproducer_generation"

        req = ModelSelectionRequest(
            agent_id=agent_id,
            task_type=task_type,
            programming_language=lang,
            task_complexity=complexity,
            required_context_size=16000,
            remaining_token_budget=remaining_token_budget,
            required_capabilities=task.required_capabilities,
            mode=mode,
            policy=policy,
            preferred_model_id=preferred_model_id,
        )

        return self.model_registry.select_model(req)
