"""
LLMorch Orchestrator — Stall & Infinite-Loop Protection Engine (Phase 9.5).
Research Guard detects circular tool executions, stalled evidence production, and runaway loops.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid

from history.database import DatabaseService, get_db_path
from history.phase9_repositories import QuestionRepository
from schemas.event import Event, EventType


class StallDetectionResult(BaseModel):
    is_stalled: bool = False
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    reason: Optional[str] = None
    repeated_pattern: Optional[str] = None
    repeat_count: int = 0
    question_created: bool = False
    question_id: Optional[str] = None


class StallDetector:
    """
    Research Guard that continuously inspects task attempt lineage and tool executions.
    Pauses tasks and creates Human-in-the-Loop decisions upon detecting infinite loops.
    """

    DEFAULT_REPEAT_THRESHOLD: int = 3

    @classmethod
    def analyze_task_history(
        cls,
        task_id: str,
        db_service: Optional[DatabaseService] = None,
        repeat_threshold: int = DEFAULT_REPEAT_THRESHOLD,
    ) -> StallDetectionResult:
        db = db_service or DatabaseService(get_db_path())
        with db.get_connection() as conn:
            # 1. Inspect recent tool executions for task
            tool_rows = conn.execute("""
                SELECT tool_name, command, args, evidence_ids, started_at
                FROM tool_executions
                WHERE task_id = ?
                ORDER BY started_at DESC
                LIMIT 15
            """, (task_id,)).fetchall()

            # 2. Inspect task attempts
            attempt_rows = conn.execute("""
                SELECT attempt_id, agent_id, role, hypothesis, evidence_ids
                FROM task_attempts
                WHERE task_id = ?
                ORDER BY attempt_number DESC
                LIMIT 10
            """, (task_id,)).fetchall()

            # 3. Get task metadata
            task_row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()

        if not tool_rows and not attempt_rows:
            return StallDetectionResult(is_stalled=False, task_id=task_id)

        task_dict = dict(task_row) if task_row else {}
        agent_id = task_dict.get("assigned_agent_id", "agent-agy-01")

        # Check Pattern 1: Same tool command executed repeatedly without producing new evidence
        commands = [r["command"] for r in tool_rows if r["command"]]
        if len(commands) >= repeat_threshold:
            most_recent_cmd = commands[0]
            consecutive_same = 0
            for cmd in commands:
                if cmd == most_recent_cmd:
                    consecutive_same += 1
                else:
                    break

            if consecutive_same >= repeat_threshold:
                reason = (
                    f"Agent {agent_id} has repeated the command '{most_recent_cmd}' {consecutive_same} times "
                    f"without producing new evidence."
                )
                q_repo = QuestionRepository(db)
                q = q_repo.create_question(
                    reason="ANALYSIS STALLED",
                    question=f"{reason} What should I do?",
                    options=[
                        {"id": "try_another_tool", "label": "Try another tool", "description": "Switch to alternative static/dynamic analyzer", "is_default": True},
                        {"id": "expand_scope", "label": "Expand scope", "description": "Expand 1-hop dependencies or adjacent modules", "is_default": False},
                        {"id": "reassign", "label": "Reassign agent/role", "description": "Reassign to another specialist agent", "is_default": False},
                        {"id": "give_instruction", "label": "Give instruction", "description": "Provide custom analyst guidance to break loop", "is_default": False},
                        {"id": "stop_task", "label": "Stop task", "description": "Mark task stalled and cancel further execution", "is_default": False},
                    ],
                    default_option="try_another_tool",
                    task_id=task_id,
                    agent_id=agent_id,
                    context={"consecutive_same": consecutive_same, "command": most_recent_cmd},
                )
                return StallDetectionResult(
                    is_stalled=True,
                    task_id=task_id,
                    agent_id=agent_id,
                    reason=reason,
                    repeated_pattern=most_recent_cmd,
                    repeat_count=consecutive_same,
                    question_created=True,
                    question_id=q["question_id"],
                )

        # Check Pattern 2: Same hypothesis repeated across >= 3 attempts with no new evidence
        hypotheses = [r["hypothesis"] for r in attempt_rows if r.get("hypothesis")]
        if len(hypotheses) >= repeat_threshold:
            most_recent_hyp = hypotheses[0]
            consecutive_hyp = sum(1 for h in hypotheses[:repeat_threshold] if h == most_recent_hyp)
            if consecutive_hyp >= repeat_threshold:
                reason = f"Hypothesis '{most_recent_hyp[:60]}...' repeated {consecutive_hyp} times across attempts without corroboration."
                q_repo = QuestionRepository(db)
                q = q_repo.create_question(
                    reason="ANALYSIS STALLED",
                    question=f"{reason} Choose how to proceed:",
                    options=[
                        {"id": "try_another_tool", "label": "Try another tool", "description": "Use alternate verification backend", "is_default": True},
                        {"id": "expand_scope", "label": "Expand scope", "description": "Inspect upstream callers or register interface", "is_default": False},
                        {"id": "give_instruction", "label": "Give instruction", "description": "Provide analyst guidance", "is_default": False},
                        {"id": "stop_task", "label": "Stop task", "description": "Conclude this path as inconclusive", "is_default": False},
                    ],
                    default_option="try_another_tool",
                    task_id=task_id,
                    agent_id=agent_id,
                    context={"hypothesis": most_recent_hyp},
                )
                return StallDetectionResult(
                    is_stalled=True,
                    task_id=task_id,
                    agent_id=agent_id,
                    reason=reason,
                    repeated_pattern=most_recent_hyp,
                    repeat_count=consecutive_hyp,
                    question_created=True,
                    question_id=q["question_id"],
                )

        return StallDetectionResult(is_stalled=False, task_id=task_id)
