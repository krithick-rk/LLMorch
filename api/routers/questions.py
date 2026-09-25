"""
LLMorch API — Questions & Human-in-the-Loop Decisions Router (Phase 9.5).
Authoritative endpoints for managing analyst questions, pauses, and guided decisions.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from api.models import (
    QuestionSummaryModel,
    QuestionDetailModel,
    CreateQuestionRequestModel,
    AnswerQuestionRequestModel,
    QuestionOptionModel,
    PaginatedResponse,
)
from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService
from history.phase9_repositories import QuestionRepository
from api.realtime import event_manager

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


def _to_detail(d: dict) -> QuestionDetailModel:
    raw_options = d.get("options") or []
    options = []
    for opt in raw_options:
        if isinstance(opt, dict):
            options.append(QuestionOptionModel(**opt))
        elif isinstance(opt, str):
            options.append(QuestionOptionModel(id=opt.lower().replace(" ", "_"), label=opt))

    return QuestionDetailModel(
        question_id=d["question_id"],
        run_id=d.get("run_id"),
        task_id=d.get("task_id"),
        attempt_id=d.get("attempt_id"),
        agent_id=d.get("agent_id"),
        status=d.get("status", "QUESTION_PENDING"),
        reason=d.get("reason", ""),
        question=d.get("question", ""),
        options=options,
        default_option=d.get("default_option"),
        created_at=datetime.fromisoformat(d["created_at"].replace("Z", "+00:00")) if d.get("created_at") else None,
        answered_at=datetime.fromisoformat(d["answered_at"].replace("Z", "+00:00")) if d.get("answered_at") else None,
        answer=d.get("answer"),
        analyst_id=d.get("analyst_id", "analyst"),
        context=d.get("context") or {},
    )


@router.get("", response_model=PaginatedResponse)
def list_questions(
    run_id: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: SessionInfo = Depends(require_session),
):
    """Lists questions with optional filtering by run, task, or status."""
    db = _get_db()
    repo = QuestionRepository(db)
    all_q = repo.list_questions(run_id=run_id, task_id=task_id, status=status, limit=1000)
    total = len(all_q)
    paged = all_q[offset: offset + limit]
    items = [_to_detail(q).model_dump() for q in paged]
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/{question_id}", response_model=QuestionDetailModel)
def get_question(
    question_id: str,
    session: SessionInfo = Depends(require_session),
):
    """Retrieves a single question detail by question ID."""
    db = _get_db()
    repo = QuestionRepository(db)
    q = repo.get_question(question_id)
    if not q:
        raise HTTPException(status_code=404, detail=f"Question '{question_id}' not found")
    return _to_detail(q)


@router.post("", response_model=QuestionDetailModel)
async def create_question(
    request: CreateQuestionRequestModel,
    session: SessionInfo = Depends(require_session),
):
    """Creates a new human-in-the-loop analyst question."""
    db = _get_db()
    repo = QuestionRepository(db)
    options_data = [opt.model_dump() for opt in request.options]

    created = repo.create_question(
        reason=request.reason,
        question=request.question,
        options=options_data,
        run_id=request.run_id,
        task_id=request.task_id,
        attempt_id=request.attempt_id,
        agent_id=request.agent_id,
        default_option=request.default_option,
        context=request.context,
    )

    detail = _to_detail(created)

    # Broadcast question created event
    await event_manager.broadcast(
        event_type="QUESTION_CREATED",
        entity_type="question",
        entity_id=created["question_id"],
        payload=detail.model_dump(),
    )

    return detail


@router.post("/{question_id}/answer", response_model=QuestionDetailModel)
async def answer_question(
    question_id: str,
    request: AnswerQuestionRequestModel,
    session: SessionInfo = Depends(require_session),
):
    """Submits the analyst's decision for a pending question."""
    db = _get_db()
    repo = QuestionRepository(db)
    existing = repo.get_question(question_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Question '{question_id}' not found")

    if existing.get("status") == "QUESTION_ANSWERED":
        raise HTTPException(status_code=400, detail="Question has already been answered")

    answered = repo.answer_question(
        question_id=question_id,
        answer=request.answer,
        analyst_id=request.analyst_id or session.role or "analyst",
    )

    detail = _to_detail(answered)

    # Broadcast question answered event
    await event_manager.broadcast(
        event_type="QUESTION_ANSWERED",
        entity_type="question",
        entity_id=question_id,
        payload=detail.model_dump(),
    )

    return detail


@router.post("/{question_id}/dismiss", response_model=QuestionDetailModel)
async def dismiss_question(
    question_id: str,
    session: SessionInfo = Depends(require_session),
):
    """Dismisses a question without answering."""
    db = _get_db()
    repo = QuestionRepository(db)
    existing = repo.get_question(question_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Question '{question_id}' not found")

    dismissed = repo.dismiss_question(question_id)
    detail = _to_detail(dismissed)

    await event_manager.broadcast(
        event_type="QUESTION_DISMISSED",
        entity_type="question",
        entity_id=question_id,
        payload=detail.model_dump(),
    )

    return detail
