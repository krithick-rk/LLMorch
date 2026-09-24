"""
LLMorch API — Tokens and Budgets router (Phase 9.1).
Endpoints for first-class token accounting, history, and budget configuration.
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from api.models import (
    TokenSummaryResponse,
    TokenUsageRecordResponse,
    TokenBudgetUpdateRequest,
    PaginatedResponse,
)
from api.session import require_session, SessionInfo
from api.realtime import event_manager
from history.database import get_db_path, DatabaseService
from history.repositories import TokenUsageRepository, TokenBudgetRepository, EventRepository
from token_tracker.accounting import TokenTracker
from schemas.event import Event, EventType

router = APIRouter(prefix="/api/tokens", tags=["tokens"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


def _get_tracker() -> TokenTracker:
    return TokenTracker(db_service=_get_db())


@router.get("", response_model=TokenSummaryResponse)
def get_tokens_overview(
    run_id: Optional[str] = Query(None, description="Scope by run id"),
    session: SessionInfo = Depends(require_session),
):
    tracker = _get_tracker()
    summary = tracker.get_summary(run_id=run_id)
    return TokenSummaryResponse(
        total_tokens_actual=summary.total_tokens_actual,
        total_tokens_estimated=summary.total_tokens_estimated,
        effective_total_tokens=summary.effective_total_tokens,
        input_tokens_actual=summary.input_tokens_actual,
        output_tokens_actual=summary.output_tokens_actual,
        input_tokens_estimated=summary.input_tokens_estimated,
        output_tokens_estimated=summary.output_tokens_estimated,
        token_budget=summary.token_budget,
        tokens_remaining=summary.tokens_remaining,
        status=summary.status.value,
        estimated_work_remaining=summary.estimated_work_remaining,
        by_agent=summary.by_agent,
        by_model=summary.by_model,
        by_stage=summary.by_stage,
        top_tasks=summary.top_tasks,
    )


@router.get("/history", response_model=PaginatedResponse)
def get_token_history(
    run_id: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    model_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: SessionInfo = Depends(require_session),
):
    tracker = _get_tracker()
    records = tracker.list_records(
        run_id=run_id,
        task_id=task_id,
        agent_id=agent_id,
        model_id=model_id,
        limit=limit,
        offset=offset
    )
    items = [
        TokenUsageRecordResponse(
            record_id=r.record_id,
            run_id=r.run_id,
            task_id=r.task_id,
            attempt_id=r.attempt_id,
            agent_id=r.agent_id,
            model_id=r.model_id,
            stage=r.stage,
            input_tokens_actual=r.input_tokens_actual,
            output_tokens_actual=r.output_tokens_actual,
            total_tokens_actual=r.total_tokens_actual,
            input_tokens_estimated=r.input_tokens_estimated,
            output_tokens_estimated=r.output_tokens_estimated,
            total_tokens_estimated=r.total_tokens_estimated,
            input_source=r.input_source.value,
            output_source=r.output_source.value,
            token_source=r.token_source.value,
            is_estimated=r.is_estimated,
            token_limit=r.token_limit,
            tokens_remaining=r.tokens_remaining,
            created_at=r.created_at,
        ).model_dump()
        for r in records
    ]
    return PaginatedResponse(total=len(items), limit=limit, offset=offset, items=items)


@router.get("/run/{run_id}", response_model=TokenSummaryResponse)
def get_run_tokens(run_id: str, session: SessionInfo = Depends(require_session)):
    tracker = _get_tracker()
    summary = tracker.get_summary(run_id=run_id)
    return TokenSummaryResponse(
        total_tokens_actual=summary.total_tokens_actual,
        total_tokens_estimated=summary.total_tokens_estimated,
        effective_total_tokens=summary.effective_total_tokens,
        input_tokens_actual=summary.input_tokens_actual,
        output_tokens_actual=summary.output_tokens_actual,
        input_tokens_estimated=summary.input_tokens_estimated,
        output_tokens_estimated=summary.output_tokens_estimated,
        token_budget=summary.token_budget,
        tokens_remaining=summary.tokens_remaining,
        status=summary.status.value,
        estimated_work_remaining=summary.estimated_work_remaining,
        by_agent=summary.by_agent,
        by_model=summary.by_model,
        by_stage=summary.by_stage,
        top_tasks=summary.top_tasks,
    )


@router.get("/agent/{agent_id}")
def get_agent_tokens(agent_id: str, session: SessionInfo = Depends(require_session)):
    tracker = _get_tracker()
    records = tracker.list_records(agent_id=agent_id, limit=500)
    actual = sum(r.total_tokens_actual for r in records)
    estimated = sum(r.total_tokens_estimated for r in records)
    return {
        "agent_id": agent_id,
        "total_tokens_actual": actual,
        "total_tokens_estimated": estimated,
        "effective_total": actual if actual > 0 else estimated,
        "records_count": len(records),
    }


@router.get("/model/{model_id}")
def get_model_tokens(model_id: str, session: SessionInfo = Depends(require_session)):
    tracker = _get_tracker()
    records = tracker.list_records(model_id=model_id, limit=500)
    actual = sum(r.total_tokens_actual for r in records)
    estimated = sum(r.total_tokens_estimated for r in records)
    return {
        "model_id": model_id,
        "total_tokens_actual": actual,
        "total_tokens_estimated": estimated,
        "effective_total": actual if actual > 0 else estimated,
        "records_count": len(records),
    }


@router.get("/task/{task_id}")
def get_task_tokens(task_id: str, session: SessionInfo = Depends(require_session)):
    tracker = _get_tracker()
    records = tracker.list_records(task_id=task_id, limit=100)
    actual = sum(r.total_tokens_actual for r in records)
    estimated = sum(r.total_tokens_estimated for r in records)
    return {
        "task_id": task_id,
        "total_tokens_actual": actual,
        "total_tokens_estimated": estimated,
        "effective_total": actual if actual > 0 else estimated,
        "records_count": len(records),
    }


# ─── Budgets Router Extension ────────────────────────────────────────────────

budgets_router = APIRouter(prefix="/api/budgets", tags=["budgets"])


@budgets_router.get("")
def list_budgets(
    run_id: Optional[str] = Query(None),
    session: SessionInfo = Depends(require_session),
):
    db = _get_db()
    repo = TokenBudgetRepository(db)
    return repo.list_budgets(run_id=run_id)


@budgets_router.put("")
async def update_budget(
    body: TokenBudgetUpdateRequest,
    session: SessionInfo = Depends(require_session),
):
    if body.budget_limit < 0:
        raise HTTPException(status_code=400, detail="Budget limit cannot be negative")

    db = _get_db()
    repo = TokenBudgetRepository(db)
    updated = repo.save_budget(
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        budget_limit=body.budget_limit,
        run_id=body.run_id
    )

    # Emit audit event
    evt_repo = EventRepository(db)
    event_id = evt_repo.record(Event(
        run_id=body.run_id,
        event_type=EventType.TOKEN_BUDGET_CHANGED,
        actor="analyst",
        payload={
            "scope_type": body.scope_type,
            "scope_id": body.scope_id,
            "new_limit": body.budget_limit
        }
    ))

    # Broadcast via websocket
    await event_manager.broadcast(
        event_type="TOKEN_BUDGET_CHANGED",
        entity_type="budget",
        entity_id=updated["budget_id"],
        payload=updated,
    )

    return updated
