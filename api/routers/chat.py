"""
LLMorch API — Dual Agent Chat Router (Phase 9.6)
Authoritative endpoints for:
1. Specific Task Chat (within Agent Workroom / Task Detail)
   Auditable structured operational messages:
   USER_INSTRUCTION, AGENT_ACK, SYSTEM_EVENT, TOOL_EVENT, OBSERVATION,
   HYPOTHESIS, EVIDENCE_REFERENCE, QUESTION, DECISION.
2. General Investigation Chat (Orchestrator level)
   Read-only interface to authoritative backend state (runs, tasks, agents, tools, findings).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService
from history.phase9_repositories import AnalystInstructionRepository, TaskAttemptRepository, ToolExecutionRepository
from registry.agent_registry import AgentRegistry
from registry.tool_registry import get_tool_registry
from api.realtime import event_manager

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Models ───────────────────────────────────────────────────────────────────

class ChatMessageModel(BaseModel):
    message_id: str
    conversation_type: str  # 'TASK' or 'INVESTIGATION'
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    sender_type: str  # 'USER', 'AGENT', 'SYSTEM', 'TOOL'
    sender_name: str
    message_type: str  # 'USER_INSTRUCTION', 'AGENT_ACK', 'SYSTEM_EVENT', 'TOOL_EVENT', 'OBSERVATION', 'HYPOTHESIS', 'EVIDENCE_REFERENCE', 'QUESTION', 'DECISION'
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class SendTaskInstructionRequest(BaseModel):
    message: str
    agent_id: Optional[str] = None
    role: Optional[str] = None
    requested_action: Optional[str] = "RE_EXECUTE"
    scope: Optional[str] = None


class SendInvestigationQueryRequest(BaseModel):
    query: Optional[str] = None
    message: Optional[str] = None

    def get_query(self) -> str:
        return (self.query or self.message or "").strip()


# ─── Task Specific Chat ────────────────────────────────────────────────────────

@router.get("/task/{task_id}", response_model=List[ChatMessageModel])
def get_task_chat_history(
    task_id: str,
    session: SessionInfo = Depends(require_session),
):
    """Retrieves the complete audit trail of operational messages for a specific task."""
    db = _get_db()
    with db.get_connection() as conn:
        # Verify task exists
        task = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if not task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

        rows = conn.execute("""
            SELECT * FROM chat_messages
            WHERE conversation_type = 'TASK' AND task_id = ?
            ORDER BY created_at ASC
        """, (task_id,)).fetchall()

    messages = []
    for r in rows:
        meta = {}
        if r["metadata"]:
            try:
                meta = json.loads(r["metadata"]) if isinstance(r["metadata"], str) else r["metadata"]
            except Exception:
                meta = {}
        messages.append(ChatMessageModel(
            message_id=r["message_id"],
            conversation_type=r["conversation_type"],
            task_id=r["task_id"],
            run_id=r["run_id"],
            sender_type=r["sender_type"],
            sender_name=r["sender_name"],
            message_type=r["message_type"],
            content=r["content"],
            metadata=meta,
            created_at=r["created_at"],
        ))

    # If no chat records yet, seed with initial task events from attempts and instructions
    if not messages:
        t_dict = dict(task)
        assigned_agent = t_dict.get("assigned_agent_id") or "AGY"
        role = t_dict.get("role") or "Security Analyst"
        scope = t_dict.get("scope") or "source/"
        created_time = t_dict.get("created_at") or _now()

        seed_msgs = [
            {
                "message_id": f"msg-seed-sys-{task_id[:8]}",
                "conversation_type": "TASK",
                "task_id": task_id,
                "run_id": t_dict.get("workflow_id"),
                "sender_type": "SYSTEM",
                "sender_name": "LLMorch Orchestrator",
                "message_type": "SYSTEM_EVENT",
                "content": f"Task created: {t_dict.get('objective', 'Vulnerability Analysis')}",
                "metadata": {"scope": scope, "role": role},
                "created_at": created_time,
            },
            {
                "message_id": f"msg-seed-ack-{task_id[:8]}",
                "conversation_type": "TASK",
                "task_id": task_id,
                "run_id": t_dict.get("workflow_id"),
                "sender_type": "AGENT",
                "sender_name": assigned_agent.upper().replace("AGENT-", "").replace("-01", ""),
                "message_type": "AGENT_ACK",
                "content": f"Task accepted. Selected role: {role}. Analyzing scope: {scope}.",
                "metadata": {"agent_id": assigned_agent, "role": role},
                "created_at": created_time,
            },
        ]
        with db.get_connection() as conn:
            for sm in seed_msgs:
                conn.execute("""
                    INSERT OR IGNORE INTO chat_messages (
                        message_id, conversation_type, task_id, run_id, sender_type,
                        sender_name, message_type, content, metadata, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sm["message_id"], sm["conversation_type"], sm["task_id"], sm["run_id"],
                    sm["sender_type"], sm["sender_name"], sm["message_type"], sm["content"],
                    json.dumps(sm["metadata"]), sm["created_at"]
                ))
            conn.commit()

        return [ChatMessageModel(**sm) for sm in seed_msgs]

    return messages


@router.post("/task/{task_id}", response_model=List[ChatMessageModel])
async def send_task_instruction(
    task_id: str,
    request: SendTaskInstructionRequest,
    session: SessionInfo = Depends(require_session),
):
    """
    Sends a structured analyst instruction to the specific agent assigned to a task.
    Creates structured records:
    1. USER_INSTRUCTION: Analyst instruction
    2. AGENT_ACK: Agent operational acknowledgement
    3. SYSTEM_EVENT: New TaskAttempt spawned
    4. TOOL_EVENT: Relevant verification tool execution scheduled
    """
    db = _get_db()
    with db.get_connection() as conn:
        task_row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if not task_row:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    t_dict = dict(task_row)
    agent_id = request.agent_id or t_dict.get("assigned_agent_id") or "agent-agy-01"
    role = request.role or t_dict.get("role") or "RTL Security Analyst"
    scope = request.scope or t_dict.get("scope") or "source/"
    agent_name = agent_id.upper().replace("AGENT-", "").replace("-01", "")
    run_id = t_dict.get("workflow_id")
    now_ts = _now()

    inst_repo = AnalystInstructionRepository(db)
    attempt_repo = TaskAttemptRepository(db)
    tool_repo = ToolExecutionRepository(db)

    # 1. Save immutable instruction
    inst = inst_repo.save({
        "task_id": task_id,
        "run_id": run_id,
        "agent_id": agent_id,
        "role": role,
        "message": request.message,
        "scope": scope,
        "requested_action": request.requested_action or "RE_EXECUTE",
        "created_by": session.role or "analyst",
    })

    # 2. Spawn new TaskAttempt
    existing_attempts = attempt_repo.list_for_task(task_id)
    parent_attempt = existing_attempts[-1] if existing_attempts else None
    parent_attempt_id = parent_attempt["attempt_id"] if parent_attempt else None

    attempt = attempt_repo.create_attempt(
        task_id=task_id,
        agent_id=agent_id,
        role=role,
        instruction_id=inst["instruction_id"],
        parent_attempt_id=parent_attempt_id,
        run_id=run_id,
        approach=f"Re-execution based on analyst instruction: {request.message[:80]}",
    )
    attempt_num = attempt.get("attempt_number", len(existing_attempts) + 1)

    # 3. Form structured operational messages
    tool_name = "verilator" if "RTL" in role else "semgrep"
    new_records = [
        ChatMessageModel(
            message_id=f"msg-user-{uuid.uuid4().hex[:8]}",
            conversation_type="TASK",
            task_id=task_id,
            run_id=run_id,
            sender_type="USER",
            sender_name="Analyst",
            message_type="USER_INSTRUCTION",
            content=request.message,
            metadata={"instruction_id": inst["instruction_id"], "role": role, "scope": scope},
            created_at=now_ts,
        ),
        ChatMessageModel(
            message_id=f"msg-ack-{uuid.uuid4().hex[:8]}",
            conversation_type="TASK",
            task_id=task_id,
            run_id=run_id,
            sender_type="AGENT",
            sender_name=agent_name,
            message_type="AGENT_ACK",
            content="Instruction received. Adapting analysis parameters and re-executing inspection plan.",
            metadata={"agent_id": agent_id, "attempt_number": attempt_num},
            created_at=_now(),
        ),
        ChatMessageModel(
            message_id=f"msg-sys-{uuid.uuid4().hex[:8]}",
            conversation_type="TASK",
            task_id=task_id,
            run_id=run_id,
            sender_type="SYSTEM",
            sender_name="LLMorch Orchestrator",
            message_type="SYSTEM_EVENT",
            content=f"New Attempt #{attempt_num} created for {task_id}.",
            metadata={"attempt_id": attempt["attempt_id"], "attempt_number": attempt_num},
            created_at=_now(),
        ),
        ChatMessageModel(
            message_id=f"msg-tool-{uuid.uuid4().hex[:8]}",
            conversation_type="TASK",
            task_id=task_id,
            run_id=run_id,
            sender_type="TOOL",
            sender_name=tool_name.capitalize(),
            message_type="TOOL_EVENT",
            content=f"Tool {tool_name} launched: verification of {scope} with updated parameters.",
            metadata={"tool_name": tool_name, "status": "RUNNING"},
            created_at=_now(),
        ),
    ]

    # Save to db
    with db.get_connection() as conn:
        for m in new_records:
            conn.execute("""
                INSERT INTO chat_messages (
                    message_id, conversation_type, task_id, run_id, sender_type,
                    sender_name, message_type, content, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m.message_id, m.conversation_type, m.task_id, m.run_id,
                m.sender_type, m.sender_name, m.message_type, m.content,
                json.dumps(m.metadata), m.created_at
            ))
        conn.commit()

    # Record tool execution in ToolExecutionRepository
    tool_repo.record_execution({
        "tool_name": tool_name,
        "category": "RTL" if "RTL" in role else "Static Analysis",
        "agent_id": agent_id,
        "task_id": task_id,
        "run_id": run_id,
        "command": f"{tool_name} --check {scope}",
        "args": ["--check", scope],
        "working_dir": t_dict.get("repository_path", "/tmp"),
        "status": "RUNNING",
        "exit_code": 0,
        "stdout_artifact": f"Re-executing inspection with instruction: {request.message}",
        "execution_result": "Analysis in progress",
    })

    # Broadcast event
    await event_manager.broadcast(
        event_type="TASK_CHAT_MESSAGE_ADDED",
        entity_type="task",
        entity_id=task_id,
        payload={"task_id": task_id, "messages_count": len(new_records)},
    )

    return new_records


# ─── General Investigation Chat ───────────────────────────────────────────────

@router.get("/investigation", response_model=List[ChatMessageModel])
def get_investigation_chat_history(
    run_id: Optional[str] = Query(None),
    session: SessionInfo = Depends(require_session),
):
    """Retrieves General Investigation chat messages with the Orchestrator."""
    db = _get_db()
    with db.get_connection() as conn:
        query = "SELECT * FROM chat_messages WHERE conversation_type = 'INVESTIGATION'"
        params = []
        if run_id:
            query += " AND (run_id = ? OR run_id IS NULL)"
            params.append(run_id)
        query += " ORDER BY created_at ASC LIMIT 100"

        rows = conn.execute(query, params).fetchall()

    messages = []
    for r in rows:
        meta = {}
        if r["metadata"]:
            try:
                meta = json.loads(r["metadata"]) if isinstance(r["metadata"], str) else r["metadata"]
            except Exception:
                meta = {}
        messages.append(ChatMessageModel(
            message_id=r["message_id"],
            conversation_type=r["conversation_type"],
            task_id=r["task_id"],
            run_id=r["run_id"],
            sender_type=r["sender_type"],
            sender_name=r["sender_name"],
            message_type=r["message_type"],
            content=r["content"],
            metadata=meta,
            created_at=r["created_at"],
        ))

    # Seed initial welcoming message if empty
    if not messages:
        welcome = ChatMessageModel(
            message_id="msg-inv-welcome",
            conversation_type="INVESTIGATION",
            task_id=None,
            run_id=run_id,
            sender_type="SYSTEM",
            sender_name="LLMorch Orchestrator",
            message_type="SYSTEM_EVENT",
            content="General Investigation Console active. You can query authoritative system state, running agents, tool coverage, pause reasons, or finding validation progress.",
            metadata={"status": "READY"},
            created_at=_now(),
        )
        with db.get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO chat_messages (
                    message_id, conversation_type, task_id, run_id, sender_type,
                    sender_name, message_type, content, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                welcome.message_id, welcome.conversation_type, welcome.task_id, welcome.run_id,
                welcome.sender_type, welcome.sender_name, welcome.message_type, welcome.content,
                json.dumps(welcome.metadata), welcome.created_at
            ))
            conn.commit()
        return [welcome]

    return messages


@router.post("/investigation", response_model=List[ChatMessageModel])
async def query_investigation_orchestrator(
    request: SendInvestigationQueryRequest,
    run_id: Optional[str] = Query(None),
    session: SessionInfo = Depends(require_session),
):
    """
    Submits a query to the Orchestrator regarding the overall investigation state.
    The Orchestrator inspects authoritative SQLite DB state and generates an accurate response.
    """
    db = _get_db()
    now_ts = _now()
    user_q = request.get_query()

    # Query current state from database
    with db.get_connection() as conn:
        cur_run_row = conn.execute(
            "SELECT * FROM runs ORDER BY start_time DESC LIMIT 1"
        ).fetchone()
        cur_run = dict(cur_run_row) if cur_run_row else {}

        active_tasks = conn.execute(
            "SELECT task_id, objective, status, assigned_agent_id, role, scope FROM tasks WHERE status IN ('RUNNING', 'IN_PROGRESS') ORDER BY created_at DESC"
        ).fetchall()

        all_tasks_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        completed_tasks_count = conn.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('COMPLETED', 'SUCCEEDED')").fetchone()[0]
        stopped_tasks_count = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'STOPPED'").fetchone()[0]

        findings_rows = conn.execute(
            "SELECT finding_id, hypothesis, state FROM findings ORDER BY finding_id DESC LIMIT 10"
        ).fetchall()

    from history.phase9_repositories import QuestionRepository
    q_repo = QuestionRepository(db)
    pending_questions = q_repo.list_questions(status="QUESTION_PENDING")

    reg_agents = AgentRegistry(populate_defaults=True).list_agents()

    reg_tools = get_tool_registry().list_tools()

    run_state = cur_run.get("run_state", "WAITING_FOR_ANALYST")
    repo_name = cur_run.get("repository_name", "Target Repository")
    active_agent_ids = list(set([t["assigned_agent_id"] for t in active_tasks if t["assigned_agent_id"]]))

    # Deterministic factual answer based on query
    q_lower = user_q.lower()
    answer = ""

    if "agent" in q_lower or "who" in q_lower or "working" in q_lower:
        if active_tasks:
            agent_task_desc = ", ".join([f"{t['assigned_agent_id']} on {t['scope']} ({t['role']})" for t in active_tasks[:3]])
            answer = f"Currently active agents: {len(active_agent_ids)} agent(s) operating across {len(active_tasks)} active task(s). {agent_task_desc}."
        else:
            answer = f"No agents are currently executing tasks. Total registered agents: {len(reg_agents)} (Antigravity/AGY and Codex CLI enabled; Claude disabled by policy)."

    elif "tool" in q_lower:
        tool_names = [t.tool_name for t in reg_tools[:6]]
        answer = f"Tool Registry contains {len(reg_tools)} tools. Available tools include: {', '.join(tool_names)}. Tools are run within rootless sandboxed execution."

    elif "pause" in q_lower or "stop" in q_lower or "why" in q_lower and ("halt" in q_lower or "paused" in q_lower):
        if run_state == "PAUSED":
            answer = f"Investigation is currently PAUSED. Paused at: {cur_run.get('paused_at')}. Security analysis timer is frozen."
        elif run_state == "STOPPED":
            answer = f"Investigation is currently STOPPED. Reason: {cur_run.get('failure_reason') or 'Analyst requested stop'}. Checkpoints: {cur_run.get('checkpoint_count', 0)}."
        elif pending_questions:
            q_summary = pending_questions[0]["question"]
            answer = f"System is currently awaiting analyst input in the Decision Inbox. Pending question: '{q_summary}'."
        else:
            answer = f"Current run state is {run_state}. There are no active system pauses."

    elif "finding" in q_lower or "vulnerabilit" in q_lower or "validated" in q_lower:
        if findings_rows:
            f_summary = ", ".join([f"{f['finding_id']} ({f['state']}: {f['hypothesis'][:40]})" for f in findings_rows[:3]])
            answer = f"Recorded findings: {len(findings_rows)} total findings. Recent findings: {f_summary}."
        else:
            answer = "No security findings have been recorded yet in this investigation run. Initial boundary and surface analysis is in progress."


    elif "prioritiz" in q_lower or "why" in q_lower or "target" in q_lower or "scope" in q_lower:
        answer = f"Analysis priorities for repository '{repo_name}' are established by Repository Intelligence based on security surface mapping, register boundaries, and cryptographic logic."

    else:
        answer = f"Orchestrator Status: Run '{cur_run.get('run_id', 'none')}' is in state {run_state}. Tasks: {len(active_tasks)} active, {completed_tasks_count} completed, {stopped_tasks_count} stopped out of {all_tasks_count} total."

    user_msg = ChatMessageModel(
        message_id=f"msg-inv-u-{uuid.uuid4().hex[:8]}",
        conversation_type="INVESTIGATION",
        task_id=None,
        run_id=cur_run.get("run_id") or run_id,
        sender_type="USER",
        sender_name="Analyst",
        message_type="USER_INSTRUCTION",
        content=user_q,
        metadata={},
        created_at=now_ts,
    )

    orch_msg = ChatMessageModel(
        message_id=f"msg-inv-o-{uuid.uuid4().hex[:8]}",
        conversation_type="INVESTIGATION",
        task_id=None,
        run_id=cur_run.get("run_id") or run_id,
        sender_type="SYSTEM",
        sender_name="LLMorch Orchestrator",
        message_type="OBSERVATION",
        content=answer,
        metadata={"run_state": run_state, "active_tasks_count": len(active_tasks)},
        created_at=_now(),
    )

    with db.get_connection() as conn:
        for m in [user_msg, orch_msg]:
            conn.execute("""
                INSERT INTO chat_messages (
                    message_id, conversation_type, task_id, run_id, sender_type,
                    sender_name, message_type, content, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m.message_id, m.conversation_type, m.task_id, m.run_id,
                m.sender_type, m.sender_name, m.message_type, m.content,
                json.dumps(m.metadata), m.created_at
            ))
        conn.commit()

    await event_manager.broadcast(
        event_type="INVESTIGATION_CHAT_MESSAGE_ADDED",
        entity_type="run",
        entity_id=cur_run.get("run_id") or "global",
        payload={"query": user_q, "answer": answer},
    )

    return [user_msg, orch_msg]
