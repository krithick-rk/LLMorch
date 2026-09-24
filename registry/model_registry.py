"""
LLMorch Model Registry (Phase 9.1)
Authoritative registry for model discovery, capability matching, and agent-model compatibility.
Separates Agent identity from Model identity.
"""

from typing import Dict, List, Optional, Any, Set
from schemas.model import (
    Model,
    ModelCapability,
    TokenEstimationMethod,
    ModelSelectionMode,
    ModelPolicy,
    ModelSelectionRequest,
    ModelSelectionResult,
)
from schemas.errors import LLMorchError, ErrorCode


class ModelRegistry:
    """
    Central registry for LLM models.
    Tracks model specifications, context windows, token tracking support,
    and compatibility with agents.
    """

    def __init__(self, populate_defaults: bool = True):
        self._models: Dict[str, Model] = {}
        # agent_id -> list of model_ids
        self._agent_model_mappings: Dict[str, List[str]] = {}
        # agent_id -> default model_id
        self._agent_defaults: Dict[str, str] = {}

        if populate_defaults:
            self._register_default_models()

    def _register_default_models(self) -> None:
        """Populates default configured models for production and auxiliary agents."""
        defaults = [
            # AGY / Antigravity models
            Model(
                model_id="agy-deep-research",
                provider="antigravity",
                display_name="Antigravity Deep Research",
                context_window=128000,
                max_output_tokens=8192,
                input_token_tracking_supported=True,
                output_token_tracking_supported=True,
                token_estimation_method=TokenEstimationMethod.LOCAL_TOKENIZER,
                capabilities=[
                    ModelCapability.CODE_ANALYSIS.value,
                    ModelCapability.DEEP_REASONING.value,
                    ModelCapability.RTL_ANALYSIS.value,
                    ModelCapability.SOFTWARE_SECURITY.value,
                    ModelCapability.LONG_CONTEXT.value,
                    ModelCapability.REPRODUCER_GENERATION.value,
                ],
                cost_per_million_input=3.0,
                cost_per_million_output=15.0,
                metadata={"family": "antigravity", "tier": "flagship"},
            ),
            Model(
                model_id="agy-fast-triage",
                provider="antigravity",
                display_name="Antigravity Fast Triage",
                context_window=64000,
                max_output_tokens=4096,
                input_token_tracking_supported=True,
                output_token_tracking_supported=True,
                token_estimation_method=TokenEstimationMethod.LOCAL_TOKENIZER,
                capabilities=[
                    ModelCapability.FAST_TRIAGE.value,
                    ModelCapability.REPOSITORY_MAPPING.value,
                    ModelCapability.SYNTAX_VERIFICATION.value,
                    ModelCapability.STRUCTURED_OUTPUT.value,
                ],
                cost_per_million_input=0.5,
                cost_per_million_output=1.5,
                metadata={"family": "antigravity", "tier": "triage"},
            ),
            # Claude Code models
            Model(
                model_id="claude-3-7-sonnet",
                provider="anthropic",
                display_name="Claude 3.7 Sonnet (Hybrid Reasoning)",
                context_window=200000,
                max_output_tokens=16384,
                input_token_tracking_supported=True,
                output_token_tracking_supported=True,
                token_estimation_method=TokenEstimationMethod.LOCAL_TOKENIZER,
                capabilities=[
                    ModelCapability.CODE_ANALYSIS.value,
                    ModelCapability.DEEP_REASONING.value,
                    ModelCapability.RTL_ANALYSIS.value,
                    ModelCapability.SOFTWARE_SECURITY.value,
                    ModelCapability.LONG_CONTEXT.value,
                    ModelCapability.REPRODUCER_GENERATION.value,
                    ModelCapability.STRUCTURED_OUTPUT.value,
                ],
                cost_per_million_input=3.0,
                cost_per_million_output=15.0,
                metadata={"family": "claude", "tier": "flagship"},
            ),
            Model(
                model_id="claude-3-5-sonnet",
                provider="anthropic",
                display_name="Claude 3.5 Sonnet",
                context_window=200000,
                max_output_tokens=8192,
                input_token_tracking_supported=True,
                output_token_tracking_supported=True,
                token_estimation_method=TokenEstimationMethod.LOCAL_TOKENIZER,
                capabilities=[
                    ModelCapability.CODE_ANALYSIS.value,
                    ModelCapability.DEEP_REASONING.value,
                    ModelCapability.RTL_ANALYSIS.value,
                    ModelCapability.SOFTWARE_SECURITY.value,
                    ModelCapability.LONG_CONTEXT.value,
                    ModelCapability.REPRODUCER_GENERATION.value,
                ],
                cost_per_million_input=3.0,
                cost_per_million_output=15.0,
                metadata={"family": "claude", "tier": "standard"},
            ),
            Model(
                model_id="claude-3-5-haiku",
                provider="anthropic",
                display_name="Claude 3.5 Haiku",
                context_window=200000,
                max_output_tokens=8192,
                input_token_tracking_supported=True,
                output_token_tracking_supported=True,
                token_estimation_method=TokenEstimationMethod.LOCAL_TOKENIZER,
                capabilities=[
                    ModelCapability.FAST_TRIAGE.value,
                    ModelCapability.REPOSITORY_MAPPING.value,
                    ModelCapability.SYNTAX_VERIFICATION.value,
                    ModelCapability.STRUCTURED_OUTPUT.value,
                ],
                cost_per_million_input=0.8,
                cost_per_million_output=4.0,
                metadata={"family": "claude", "tier": "fast"},
            ),
            # Codex / OpenAI CLI models
            Model(
                model_id="gpt-4o",
                provider="openai",
                display_name="GPT-4o (Omni)",
                context_window=128000,
                max_output_tokens=16384,
                input_token_tracking_supported=True,
                output_token_tracking_supported=True,
                token_estimation_method=TokenEstimationMethod.ACTUAL_TOKENIZER,
                capabilities=[
                    ModelCapability.CODE_ANALYSIS.value,
                    ModelCapability.SOFTWARE_SECURITY.value,
                    ModelCapability.REPRODUCER_GENERATION.value,
                    ModelCapability.STRUCTURED_OUTPUT.value,
                    ModelCapability.LONG_CONTEXT.value,
                ],
                cost_per_million_input=2.5,
                cost_per_million_output=10.0,
                metadata={"family": "openai", "tier": "flagship"},
            ),
            Model(
                model_id="o1",
                provider="openai",
                display_name="OpenAI o1 (Deep Reasoning)",
                context_window=200000,
                max_output_tokens=32768,
                input_token_tracking_supported=True,
                output_token_tracking_supported=True,
                token_estimation_method=TokenEstimationMethod.ACTUAL_TOKENIZER,
                capabilities=[
                    ModelCapability.DEEP_REASONING.value,
                    ModelCapability.CODE_ANALYSIS.value,
                    ModelCapability.RTL_ANALYSIS.value,
                    ModelCapability.SOFTWARE_SECURITY.value,
                    ModelCapability.LONG_CONTEXT.value,
                ],
                cost_per_million_input=15.0,
                cost_per_million_output=60.0,
                metadata={"family": "openai", "tier": "reasoning"},
            ),
            Model(
                model_id="o3-mini",
                provider="openai",
                display_name="OpenAI o3-mini (Reasoning Code/STEM)",
                context_window=200000,
                max_output_tokens=65536,
                input_token_tracking_supported=True,
                output_token_tracking_supported=True,
                token_estimation_method=TokenEstimationMethod.ACTUAL_TOKENIZER,
                capabilities=[
                    ModelCapability.DEEP_REASONING.value,
                    ModelCapability.FAST_TRIAGE.value,
                    ModelCapability.CODE_ANALYSIS.value,
                    ModelCapability.RTL_ANALYSIS.value,
                    ModelCapability.STRUCTURED_OUTPUT.value,
                ],
                cost_per_million_input=1.1,
                cost_per_million_output=4.4,
                metadata={"family": "openai", "tier": "reasoning_fast"},
            ),
            # Auxiliary / Mock models
            Model(
                model_id="mock-reasoning",
                provider="auxiliary",
                display_name="Controlled Mock Deep Reasoning",
                context_window=128000,
                max_output_tokens=8192,
                input_token_tracking_supported=True,
                output_token_tracking_supported=True,
                token_estimation_method=TokenEstimationMethod.HEURISTIC_ESTIMATE,
                capabilities=[
                    ModelCapability.CODE_ANALYSIS.value,
                    ModelCapability.DEEP_REASONING.value,
                    ModelCapability.RTL_ANALYSIS.value,
                    ModelCapability.SOFTWARE_SECURITY.value,
                    ModelCapability.REPRODUCER_GENERATION.value,
                ],
                cost_per_million_input=0.0,
                cost_per_million_output=0.0,
                metadata={"family": "mock", "tier": "test"},
            ),
            Model(
                model_id="mock-fast",
                provider="auxiliary",
                display_name="Controlled Mock Fast Triage",
                context_window=64000,
                max_output_tokens=4096,
                input_token_tracking_supported=True,
                output_token_tracking_supported=True,
                token_estimation_method=TokenEstimationMethod.HEURISTIC_ESTIMATE,
                capabilities=[
                    ModelCapability.FAST_TRIAGE.value,
                    ModelCapability.REPOSITORY_MAPPING.value,
                    ModelCapability.SYNTAX_VERIFICATION.value,
                ],
                cost_per_million_input=0.0,
                cost_per_million_output=0.0,
                metadata={"family": "mock", "tier": "test_fast"},
            ),
        ]

        for m in defaults:
            self.register_model(m)

        # Establish Agent-to-Model mappings
        self.bind_models_to_agent("agent-agy-01", ["agy-deep-research", "agy-fast-triage"], default_model_id="agy-deep-research")
        self.bind_models_to_agent("agent-claude-01", ["claude-3-7-sonnet", "claude-3-5-sonnet", "claude-3-5-haiku"], default_model_id="claude-3-7-sonnet")
        self.bind_models_to_agent("agent-codex-01", ["gpt-4o", "o3-mini", "o1"], default_model_id="gpt-4o")
        self.bind_models_to_agent("agent-fourth-01", ["mock-reasoning", "mock-fast"], default_model_id="mock-reasoning")

    def register_model(self, model: Model) -> Model:
        """Registers a model in the registry."""
        self._models[model.model_id] = model
        return model

    def unregister_model(self, model_id: str) -> Optional[Model]:
        """Removes a model from the registry."""
        return self._models.pop(model_id, None)

    def get_model(self, model_id: str) -> Optional[Model]:
        """Retrieves a model by its identifier."""
        return self._models.get(model_id)

    def list_models(
        self,
        provider: Optional[str] = None,
        capability: Optional[str] = None,
        enabled_only: bool = True
    ) -> List[Model]:
        """Lists models matching optional filters."""
        models = list(self._models.values())
        if enabled_only:
            models = [m for m in models if m.enabled]
        if provider:
            models = [m for m in models if m.provider.lower() == provider.lower()]
        if capability:
            models = [m for m in models if capability in m.capabilities]
        return models

    def bind_models_to_agent(
        self,
        agent_id: str,
        model_ids: List[str],
        default_model_id: Optional[str] = None
    ) -> None:
        """Binds a list of supported models to an agent."""
        valid_ids = [m for m in model_ids if m in self._models]
        self._agent_model_mappings[agent_id] = valid_ids
        if default_model_id and default_model_id in self._models:
            self._agent_defaults[agent_id] = default_model_id
        elif valid_ids and agent_id not in self._agent_defaults:
            self._agent_defaults[agent_id] = valid_ids[0]

    def get_models_for_agent(self, agent_id: str) -> List[Model]:
        """Returns all models configured for a specific agent."""
        model_ids = self._agent_model_mappings.get(agent_id, [])
        return [self._models[m] for m in model_ids if m in self._models]

    def get_default_model_for_agent(self, agent_id: str) -> Optional[Model]:
        """Returns the default configured model for an agent."""
        default_id = self._agent_defaults.get(agent_id)
        if default_id and default_id in self._models:
            return self._models[default_id]
        models = self.get_models_for_agent(agent_id)
        return models[0] if models else None

    def is_model_supported_by_agent(self, agent_id: str, model_id: str) -> bool:
        """Validates whether a specific agent can execute with a specific model."""
        allowed = self._agent_model_mappings.get(agent_id, [])
        return model_id in allowed

    def select_model(self, request: ModelSelectionRequest) -> ModelSelectionResult:
        """
        Data-driven model selection engine.
        Supports AUTO, MANUAL, and POLICY modes.
        Enforces agent compatibility and capability matching without inventing quality scores.
        """
        candidate_models: List[Model] = []
        if request.agent_id:
            candidate_models = self.get_models_for_agent(request.agent_id)
        else:
            candidate_models = self.list_models(enabled_only=True)

        if not candidate_models:
            raise LLMorchError(
                f"No available models found for agent '{request.agent_id}'",
                code=ErrorCode.MODEL_UNAVAILABLE if hasattr(ErrorCode, "MODEL_UNAVAILABLE") else ErrorCode.AGENT_UNAVAILABLE
            )

        # 1. MANUAL Mode
        if request.mode == ModelSelectionMode.MANUAL:
            target_id = request.preferred_model_id
            if not target_id:
                raise LLMorchError("Manual model selection requires preferred_model_id", code=ErrorCode.INVALID_STATE_TRANSITION)
            model = self.get_model(target_id)
            if not model or not model.enabled:
                raise LLMorchError(f"Model '{target_id}' is not available or disabled", code=ErrorCode.INVALID_STATE_TRANSITION)
            if request.agent_id and not self.is_model_supported_by_agent(request.agent_id, target_id):
                raise LLMorchError(
                    f"Model '{target_id}' is not supported by agent '{request.agent_id}'",
                    code=ErrorCode.INVALID_STATE_TRANSITION
                )
            return ModelSelectionResult(
                selected_model=model,
                agent_id=request.agent_id,
                selection_mode=ModelSelectionMode.MANUAL,
                selection_reason=f"Manually selected model '{model.display_name}' by analyst.",
                fallback_models=[m.model_id for m in candidate_models if m.model_id != model.model_id]
            )

        # 2. POLICY Mode
        if request.mode == ModelSelectionMode.POLICY and request.policy:
            policy_caps_map: Dict[ModelPolicy, List[str]] = {
                ModelPolicy.BALANCED: [ModelCapability.CODE_ANALYSIS.value],
                ModelPolicy.DEEP_ANALYSIS: [ModelCapability.DEEP_REASONING.value, ModelCapability.CODE_ANALYSIS.value],
                ModelPolicy.LOW_TOKEN: [ModelCapability.FAST_TRIAGE.value],
                ModelPolicy.FAST_TRIAGE: [ModelCapability.FAST_TRIAGE.value],
                ModelPolicy.REPOSITORY_MAPPING: [ModelCapability.REPOSITORY_MAPPING.value],
                ModelPolicy.RTL_SECURITY: [ModelCapability.RTL_ANALYSIS.value, ModelCapability.DEEP_REASONING.value],
                ModelPolicy.SOFTWARE_SECURITY: [ModelCapability.SOFTWARE_SECURITY.value, ModelCapability.CODE_ANALYSIS.value],
            }
            required_caps = policy_caps_map.get(request.policy, [ModelCapability.CODE_ANALYSIS.value])

            # Filter candidates that satisfy required capabilities
            matching = [
                m for m in candidate_models
                if all(cap in m.capabilities for cap in required_caps)
                and m.context_window >= request.required_context_size
            ]
            if not matching:
                # Relax context requirement if needed
                matching = [m for m in candidate_models if any(cap in m.capabilities for cap in required_caps)]
            selected = matching[0] if matching else candidate_models[0]

            return ModelSelectionResult(
                selected_model=selected,
                agent_id=request.agent_id,
                selection_mode=ModelSelectionMode.POLICY,
                selection_reason=f"Selected '{selected.display_name}' resolving policy {request.policy.value} (required: {required_caps}).",
                fallback_models=[m.model_id for m in candidate_models if m.model_id != selected.model_id]
            )

        # 3. AUTO Mode
        # Derive requirements from task type, language, complexity, and context size
        required_caps: Set[str] = set(request.required_capabilities)
        if request.task_type:
            tt = request.task_type.lower()
            if "rtl" in tt or "hardware" in tt or "verilog" in tt:
                required_caps.add(ModelCapability.RTL_ANALYSIS.value)
            if "triage" in tt or "mapping" in tt or "intake" in tt:
                required_caps.add(ModelCapability.FAST_TRIAGE.value)
            if "repro" in tt or "validation" in tt:
                required_caps.add(ModelCapability.REPRODUCER_GENERATION.value)
            if "deep" in tt or "complex" in tt:
                required_caps.add(ModelCapability.DEEP_REASONING.value)

        if request.programming_language:
            lang = request.programming_language.lower()
            if lang in ("systemverilog", "verilog", "vhdl"):
                required_caps.add(ModelCapability.RTL_ANALYSIS.value)

        if request.task_complexity in ("high", "critical"):
            required_caps.add(ModelCapability.DEEP_REASONING.value)

        # Filter by capabilities and context window
        matching = [
            m for m in candidate_models
            if required_caps.issubset(set(m.capabilities))
            and m.context_window >= request.required_context_size
        ]

        if not matching:
            # Fallback to partial capability match
            scored = []
            for m in candidate_models:
                score = len(required_caps.intersection(set(m.capabilities)))
                scored.append((score, m))
            scored.sort(key=lambda x: x[0], reverse=True)
            selected = scored[0][1] if scored else candidate_models[0]
        else:
            # For low-complexity tasks or low token budget, prefer smaller/faster model
            if request.task_complexity == "low" or (request.remaining_token_budget and request.remaining_token_budget < 30000):
                fast_models = [m for m in matching if ModelCapability.FAST_TRIAGE.value in m.capabilities]
                selected = fast_models[0] if fast_models else matching[0]
            else:
                selected = matching[0]

        reason = (
            f"Auto-selected '{selected.display_name}' matching capabilities {list(required_caps)} "
            f"for task complexity '{request.task_complexity}' and context {request.required_context_size}."
        )

        return ModelSelectionResult(
            selected_model=selected,
            agent_id=request.agent_id,
            selection_mode=ModelSelectionMode.AUTO,
            selection_reason=reason,
            fallback_models=[m.model_id for m in candidate_models if m.model_id != selected.model_id]
        )
