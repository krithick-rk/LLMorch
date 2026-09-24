"""
LLMorch Token Accounting Engine (Phase 9.1)
First-class token accounting subsystem for every agent, model, task, run, and stage.
Differentiates between actual telemetry and estimated usage.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import uuid

from schemas.token import (
    TokenUsageRecord,
    TokenSource,
    TokenLimitStatus,
    TokenAccountingSummary,
    TokenBudgetConfig,
)
from schemas.event import Event, EventType
from history.database import DatabaseService, get_db_path
from history.repositories import TokenUsageRepository, TokenBudgetRepository, EventRepository

logger = logging.getLogger(__name__)


def estimate_tokens_from_text(text: str, is_code: bool = True) -> int:
    """
    Deterministic local tokenizer for code and text when provider telemetry is absent.
    Level 1: tiktoken if installed.
    Level 2: deterministic code/text ratio (chars / 3.6 for code, chars / 4.0 for prose).
    """
    if not text:
        return 0
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        pass

    # Deterministic fallback heuristic
    ratio = 3.6 if is_code else 4.0
    return max(1, int(len(text) / ratio))


class TokenTracker:
    """
    Central authoritative token tracker for LLMorch.
    Enforces that token estimates are never conflated with authoritative provider telemetry.
    """

    def __init__(self, db_service: Optional[DatabaseService] = None, budget_config: Optional[TokenBudgetConfig] = None):
        self.db = db_service or DatabaseService(get_db_path())
        self.usage_repo = TokenUsageRepository(self.db)
        self.budget_repo = TokenBudgetRepository(self.db)
        self.event_repo = EventRepository(self.db)
        self.config = budget_config or TokenBudgetConfig()

    def record_usage(
        self,
        task_id: str,
        run_id: str,
        agent_id: str,
        model_id: str,
        stage: str = "investigation",
        input_tokens_actual: int = 0,
        output_tokens_actual: int = 0,
        input_tokens_estimated: int = 0,
        output_tokens_estimated: int = 0,
        raw_input_text: Optional[str] = None,
        raw_output_text: Optional[str] = None,
        token_source: TokenSource = TokenSource.UNKNOWN,
        is_estimated: bool = False,
        attempt_id: Optional[str] = None,
        event_callback: Optional[Any] = None
    ) -> TokenUsageRecord:
        """
        Appends a verifiable token usage record to persistent history.
        If actual counts are missing but raw text is supplied, estimates locally and tags as ESTIMATED.
        """
        # If actual telemetry is not reported, compute local estimate
        if input_tokens_actual == 0 and raw_input_text:
            input_tokens_estimated = estimate_tokens_from_text(raw_input_text, is_code=True)
            token_source = TokenSource.LOCAL_TOKENIZER
            is_estimated = True

        if output_tokens_actual == 0 and raw_output_text:
            output_tokens_estimated = estimate_tokens_from_text(raw_output_text, is_code=True)
            if token_source == TokenSource.UNKNOWN:
                token_source = TokenSource.LOCAL_TOKENIZER
            is_estimated = True

        tot_actual = input_tokens_actual + output_tokens_actual
        tot_estimated = input_tokens_estimated + output_tokens_estimated

        # Look up or use run budget
        budget_row = self.budget_repo.get_budget("run", run_id)
        run_budget = budget_row["budget_limit"] if budget_row else self.config.run_budget

        # Aggregate current usage for run to compute remaining
        summary = self.usage_repo.get_summary(run_id=run_id, budget=run_budget)
        consumed_so_far = summary.effective_total_tokens + (tot_actual if tot_actual > 0 else tot_estimated)
        remaining = max(0, run_budget - consumed_so_far)

        # Update budget record
        self.budget_repo.save_budget(
            scope_type="run",
            scope_id=run_id,
            budget_limit=run_budget,
            consumed=consumed_so_far,
            run_id=run_id
        )

        record = TokenUsageRecord(
            record_id=f"tok-{uuid.uuid4().hex[:12]}",
            run_id=run_id,
            task_id=task_id,
            attempt_id=attempt_id,
            agent_id=agent_id,
            model_id=model_id,
            stage=stage,
            input_tokens_actual=input_tokens_actual,
            output_tokens_actual=output_tokens_actual,
            total_tokens_actual=tot_actual,
            input_tokens_estimated=input_tokens_estimated,
            output_tokens_estimated=output_tokens_estimated,
            total_tokens_estimated=tot_estimated,
            input_source=token_source if input_tokens_actual > 0 else (TokenSource.LOCAL_TOKENIZER if input_tokens_estimated > 0 else TokenSource.UNKNOWN),
            output_source=token_source if output_tokens_actual > 0 else (TokenSource.LOCAL_TOKENIZER if output_tokens_estimated > 0 else TokenSource.UNKNOWN),
            token_source=token_source,
            is_estimated=is_estimated,
            token_limit=run_budget,
            tokens_remaining=remaining,
        )

        saved = self.usage_repo.save(record)

        # Record audit event
        audit_event = Event(
            run_id=run_id,
            event_type=EventType.TOKEN_USAGE_UPDATED,
            actor="token_tracker",
            payload={
                "task_id": task_id,
                "agent_id": agent_id,
                "model_id": model_id,
                "tokens_recorded": tot_actual if tot_actual > 0 else tot_estimated,
                "is_estimated": is_estimated,
                "token_source": token_source.value,
                "run_budget": run_budget,
                "tokens_remaining": remaining,
            }
        )
        self.event_repo.record(audit_event)

        # Check threshold warnings
        pct_rem = (remaining / run_budget * 100.0) if run_budget > 0 else 0.0
        if remaining == 0:
            self.event_repo.record(Event(
                run_id=run_id,
                event_type=EventType.BUDGET_EXHAUSTED,
                actor="token_tracker",
                payload={"run_id": run_id, "consumed": consumed_so_far, "limit": run_budget}
            ))
        elif pct_rem <= self.config.near_limit_threshold_percent:
            self.event_repo.record(Event(
                run_id=run_id,
                event_type=EventType.TOKEN_LIMIT_WARNING,
                actor="token_tracker",
                payload={"run_id": run_id, "pct_remaining": pct_rem, "severity": "NEAR_LIMIT"}
            ))
        elif pct_rem <= self.config.low_threshold_percent:
            self.event_repo.record(Event(
                run_id=run_id,
                event_type=EventType.BUDGET_WARNING,
                actor="token_tracker",
                payload={"run_id": run_id, "pct_remaining": pct_rem, "severity": "LOW"}
            ))

        if event_callback:
            try:
                event_callback(audit_event)
            except Exception as e:
                logger.warning(f"Error in token tracker event callback: {e}")

        return saved

    def get_summary(self, run_id: Optional[str] = None) -> TokenAccountingSummary:
        budget_row = self.budget_repo.get_budget("run", run_id or "global")
        budget = budget_row["budget_limit"] if budget_row else self.config.run_budget
        return self.usage_repo.get_summary(run_id=run_id, budget=budget)

    def list_records(
        self,
        run_id: Optional[str] = None,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        model_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[TokenUsageRecord]:
        return self.usage_repo.list_records(
            run_id=run_id,
            task_id=task_id,
            agent_id=agent_id,
            model_id=model_id,
            limit=limit,
            offset=offset
        )
