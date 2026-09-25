"""
LLMorch — Analyst Question & Human-in-the-Loop Schemas (Phase 9.5)
Defines the authoritative question lifecycle model for interactive agent decisions.
"""

from enum import Enum
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class QuestionStatus(str, Enum):
    QUESTION_PENDING = "QUESTION_PENDING"
    QUESTION_VIEWED = "QUESTION_VIEWED"
    QUESTION_ANSWERED = "QUESTION_ANSWERED"
    QUESTION_DISMISSED = "QUESTION_DISMISSED"
    QUESTION_EXPIRED = "QUESTION_EXPIRED"
    AUTO_RESOLVED = "AUTO_RESOLVED"


class QuestionOption(BaseModel):
    id: str
    label: str
    description: Optional[str] = None
    is_default: bool = False


class AnalystQuestion(BaseModel):
    question_id: str = Field(..., description="Unique question identifier, e.g. Q-1001 or uuid")
    run_id: Optional[str] = None
    task_id: Optional[str] = None
    attempt_id: Optional[str] = None
    agent_id: Optional[str] = None
    status: QuestionStatus = QuestionStatus.QUESTION_PENDING
    reason: str = Field(..., description="Why analyst guidance is needed (e.g. Empty file, Conflicting evidence, Stalled analysis)")
    question: str = Field(..., description="The question text presented to analyst")
    options: List[QuestionOption] = Field(default_factory=list, description="Available action options for analyst")
    default_option: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    answered_at: Optional[datetime] = None
    answer: Optional[str] = None
    analyst_id: Optional[str] = "analyst"
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CreateQuestionRequest(BaseModel):
    run_id: Optional[str] = None
    task_id: Optional[str] = None
    attempt_id: Optional[str] = None
    agent_id: Optional[str] = None
    reason: str
    question: str
    options: List[QuestionOption]
    default_option: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class AnswerQuestionRequest(BaseModel):
    answer: str
    reasoning: Optional[str] = None
    analyst_id: Optional[str] = "analyst"


class QuestionSummary(BaseModel):
    question_id: str
    run_id: Optional[str] = None
    task_id: Optional[str] = None
    attempt_id: Optional[str] = None
    agent_id: Optional[str] = None
    status: QuestionStatus
    reason: str
    question: str
    options: List[QuestionOption]
    default_option: Optional[str] = None
    created_at: datetime
    answered_at: Optional[datetime] = None
    answer: Optional[str] = None
