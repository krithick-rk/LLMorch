"""
LLMorch Explicit Task State Machine, Lifecycle & Watchdog Contracts
Defines full task states, attempt lineage, watchdog controls, and budget monitoring.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ExplicitTaskState(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    WAITING_FOR_CONTEXT = "WAITING_FOR_CONTEXT"
    WAITING_FOR_AGENT = "WAITING_FOR_AGENT"
    WAITING_FOR_TOOL = "WAITING_FOR_TOOL"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    SUCCEEDED = "SUCCEEDED"
    UNRESOLVED = "UNRESOLVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


# Legal transitions matrix
LEGAL_TASK_TRANSITIONS: Dict[ExplicitTaskState, List[ExplicitTaskState]] = {
    ExplicitTaskState.CREATED: [ExplicitTaskState.QUEUED, ExplicitTaskState.PLANNING, ExplicitTaskState.CANCELLED],
    ExplicitTaskState.QUEUED: [ExplicitTaskState.PLANNING, ExplicitTaskState.WAITING_FOR_CONTEXT, ExplicitTaskState.WAITING_FOR_AGENT, ExplicitTaskState.CANCELLED],
    ExplicitTaskState.PLANNING: [ExplicitTaskState.WAITING_FOR_CONTEXT, ExplicitTaskState.WAITING_FOR_AGENT, ExplicitTaskState.WAITING_FOR_HUMAN, ExplicitTaskState.BLOCKED, ExplicitTaskState.FAILED],
    ExplicitTaskState.WAITING_FOR_CONTEXT: [ExplicitTaskState.WAITING_FOR_AGENT, ExplicitTaskState.WAITING_FOR_TOOL, ExplicitTaskState.RUNNING, ExplicitTaskState.BLOCKED, ExplicitTaskState.FAILED],
    ExplicitTaskState.WAITING_FOR_AGENT: [ExplicitTaskState.RUNNING, ExplicitTaskState.WAITING_FOR_TOOL, ExplicitTaskState.BLOCKED, ExplicitTaskState.PAUSED, ExplicitTaskState.CANCELLED],
    ExplicitTaskState.WAITING_FOR_TOOL: [ExplicitTaskState.RUNNING, ExplicitTaskState.BLOCKED, ExplicitTaskState.FAILED, ExplicitTaskState.PAUSED],
    ExplicitTaskState.RUNNING: [ExplicitTaskState.PAUSED, ExplicitTaskState.WAITING_FOR_HUMAN, ExplicitTaskState.BLOCKED, ExplicitTaskState.FAILED, ExplicitTaskState.SUCCEEDED, ExplicitTaskState.UNRESOLVED],
    ExplicitTaskState.PAUSED: [ExplicitTaskState.RUNNING, ExplicitTaskState.CANCELLED, ExplicitTaskState.REJECTED],
    ExplicitTaskState.WAITING_FOR_HUMAN: [ExplicitTaskState.RUNNING, ExplicitTaskState.QUEUED, ExplicitTaskState.BLOCKED, ExplicitTaskState.CANCELLED, ExplicitTaskState.REJECTED],
    ExplicitTaskState.BLOCKED: [ExplicitTaskState.QUEUED, ExplicitTaskState.WAITING_FOR_HUMAN, ExplicitTaskState.FAILED, ExplicitTaskState.CANCELLED],
    ExplicitTaskState.FAILED: [ExplicitTaskState.QUEUED, ExplicitTaskState.REJECTED],  # Retry allows FAILED -> QUEUED
    ExplicitTaskState.UNRESOLVED: [ExplicitTaskState.QUEUED, ExplicitTaskState.WAITING_FOR_HUMAN, ExplicitTaskState.CANCELLED],
    ExplicitTaskState.SUCCEEDED: [],  # Terminal
    ExplicitTaskState.REJECTED: [],   # Terminal
    ExplicitTaskState.CANCELLED: [],  # Terminal
}


def is_legal_transition(from_state: ExplicitTaskState, to_state: ExplicitTaskState) -> bool:
    """Returns True if transition from from_state to to_state is allowed."""
    return to_state in LEGAL_TASK_TRANSITIONS.get(from_state, [])


class TaskWatchdogConfig(BaseModel):
    timeout_seconds: int = 600
    stale_heartbeat_seconds: int = 60
    max_retries: int = 3
    max_tool_executions: int = 15
    max_agent_switches: int = 3
    max_questions: int = 2
    max_replan_depth: int = 2
    token_budget: int = 100000
    context_budget_bytes: int = 500000


class TaskAttemptRecord(BaseModel):
    attempt_id: str = Field(default_factory=lambda: f"att-{uuid.uuid4().hex[:8]}")
    task_id: str
    attempt_number: int = 1
    parent_attempt_id: Optional[str] = None
    run_id: Optional[str] = None
    agent_id: str
    role: str
    model_id: Optional[str] = None
    method: str = "Automated Verification"
    tools: List[str] = Field(default_factory=list)
    context_pack_id: Optional[str] = None
    token_budget: int = 50000
    tokens_used: int = 0
    start_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    heartbeat_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: Optional[str] = None
    commands: List[str] = Field(default_factory=list)
    artifacts: List[str] = Field(default_factory=list)
    logs: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    failure_reason: Optional[str] = None
    failure_code: Optional[str] = None
    analyst_modifications: Optional[str] = None
    status: str = "RUNNING"  # RUNNING, SUCCEEDED, FAILED, TIMED_OUT, STALLED, CANCELLED


class TaskDiagnosticSummary(BaseModel):
    task_id: str
    objective: str
    why_objective: str
    agent_id: str
    role: str
    model_id: Optional[str] = None
    method: str
    tools: List[str]
    context_summary: str
    steps_executed: List[str]
    commands_run: List[str]
    what_failed: Optional[str] = None
    where_failed: Optional[str] = None
    what_is_known: List[str] = Field(default_factory=list)
    what_is_unknown: List[str] = Field(default_factory=list)
    reason_for_state: str
    timeline: List[Dict[str, str]] = Field(default_factory=list)
    suggested_actions: List[Dict[str, str]] = Field(default_factory=list)
    attempts: List[Dict[str, Any]] = Field(default_factory=list)
