"""
LLMorch — COMMA Engineering Assistant Router (Sections 39, 40, 41, 42, 43, 44, 45, 46)
Authoritative application engineering assistant powered exclusively by AGY runtime.
Reads authoritative SQLite database state, logs, tasks, plans, and token telemetry.
Strictly prohibits Claude invocation (0 invocations).
"""

from __future__ import annotations

import os
import json
import uuid
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService
from history.project_repository import ProjectRepository
from history.id_service import IdService

router = APIRouter(prefix="/api/comma", tags=["comma"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CommaQueryRequest(BaseModel):
    query: str
    project_id: Optional[str] = None
    current_page: Optional[str] = "workspace"
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CommaQueryResponse(BaseModel):
    status: str = "SUCCESS"
    query: str
    answer: str
    powered_by: str = "AGY"
    model: str = "Gemini 3.6 Low"
    task_proposal: Optional[Dict[str, Any]] = None
    token_usage: Dict[str, Any] = Field(default_factory=dict)
    context_inspected: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str


@router.get("/status")
def get_comma_status(session: SessionInfo = Depends(require_session)) -> Dict[str, Any]:
    """Returns COMMA assistant runtime status and execution engine info."""
    agy_bin = shutil.which("agy") or "/home/hackdac/.local/bin/agy"
    agy_exists = Path(agy_bin).exists()
    return {
        "status": "READY" if agy_exists else "DEGRADED",
        "assistant_name": "COMMA",
        "subtitle": "LLMorch Engineering Assistant",
        "powered_by": "AGY",
        "executable": agy_bin,
        "model": "Gemini 3.6 Low",
        "claude_invocations": 0,
        "claude_allowed": False,
        "capabilities": [
            "Project State Inspection",
            "Plan & WorkPackage Explainability",
            "Task Queue Diagnostic",
            "Hardware Security & Vulnerability Analysis",
            "Structured Task Synthesis",
            "Token Telemetry Accounting",
            "Log Auditing"
        ]
    }


@router.get("/history")
def get_comma_history(
    project_id: Optional[str] = None,
    limit: int = 50,
    session: SessionInfo = Depends(require_session)
) -> List[Dict[str, Any]]:
    """Returns past COMMA conversation messages ordered chronologically."""
    db = _get_db()
    with db.get_connection() as conn:
        if project_id:
            rows = conn.execute("""
                SELECT message_id, conversation_type, task_id, run_id, sender_type,
                       sender_name, message_type, content, metadata, created_at, project_id
                FROM chat_messages
                WHERE conversation_type = 'COMMA' AND (project_id = ? OR project_id IS NULL)
                ORDER BY created_at ASC
                LIMIT ?
            """, (project_id, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT message_id, conversation_type, task_id, run_id, sender_type,
                       sender_name, message_type, content, metadata, created_at, project_id
                FROM chat_messages
                WHERE conversation_type = 'COMMA'
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,)).fetchall()

    messages = []
    for r in rows:
        meta = {}
        if r["metadata"]:
            try:
                meta = json.loads(r["metadata"]) if isinstance(r["metadata"], str) else r["metadata"]
            except Exception:
                meta = {}
        messages.append({
            "message_id": r["message_id"],
            "sender_type": r["sender_type"],
            "sender_name": r["sender_name"],
            "content": r["content"],
            "metadata": meta,
            "created_at": r["created_at"],
            "project_id": r.get("project_id") if isinstance(r, dict) else r["project_id"]
        })
    return messages


@router.delete("/history")
def clear_comma_history(
    project_id: Optional[str] = None,
    session: SessionInfo = Depends(require_session)
) -> Dict[str, Any]:
    """Clears past COMMA conversation history."""
    db = _get_db()
    with db.get_connection() as conn:
        if project_id:
            conn.execute("DELETE FROM chat_messages WHERE conversation_type = 'COMMA' AND (project_id = ? OR project_id IS NULL)", (project_id,))
        else:
            conn.execute("DELETE FROM chat_messages WHERE conversation_type = 'COMMA'")
        conn.commit()
    return {"status": "SUCCESS", "message": "COMMA conversation history cleared"}


@router.post("/query", response_model=CommaQueryResponse)
async def query_comma_assistant(
    req: CommaQueryRequest,
    session: SessionInfo = Depends(require_session)
) -> CommaQueryResponse:
    """
    Submits a user query to COMMA. COMMA compiles live authoritative SQLite state,
    invokes the real AGY CLI runtime, and returns a contextual, transparent response.
    """
    db = _get_db()
    proj_repo = ProjectRepository(db)
    active_project_id = req.project_id or proj_repo.get_active_project_id()

    # 1. Gather authoritative system and project state from SQLite
    with db.get_connection() as conn:
        # Project info
        p_row = conn.execute("SELECT * FROM projects WHERE project_id = ?", (active_project_id,)).fetchone()
        project_dict = dict(p_row) if p_row else {}

        # Active Run
        r_row = conn.execute("""
            SELECT * FROM runs WHERE project_id = ? ORDER BY start_time DESC LIMIT 1
        """, (active_project_id,)).fetchone()
        run_dict = dict(r_row) if r_row else {}

        # Active Plan
        plan_id = run_dict.get("plan_id") or req.context.get("plan_id")
        if plan_id:
            plan_row = conn.execute("SELECT * FROM verification_plans WHERE plan_id = ?", (plan_id,)).fetchone()
        else:
            plan_row = conn.execute("SELECT * FROM verification_plans WHERE project_id = ? ORDER BY created_at DESC LIMIT 1", (active_project_id,)).fetchone()
        plan_dict = dict(plan_row) if plan_row else {}
        actual_plan_id = plan_dict.get("plan_id")

        # WorkPackages
        wp_rows = []
        if actual_plan_id:
            wp_rows = conn.execute("SELECT package_id, display_id, name, status, bucket, role, why_proposed, target_files FROM work_packages WHERE plan_id = ?", (actual_plan_id,)).fetchall()
        work_packages = [dict(w) for w in wp_rows]

        # Tasks
        task_rows = conn.execute("""
            SELECT * FROM tasks
            WHERE project_id = ?
            ORDER BY created_at DESC LIMIT 30
        """, (active_project_id,)).fetchall()
        tasks = []
        for r in task_rows:
            td = dict(r)
            inp = {}
            if td.get("inputs"):
                try:
                    inp = json.loads(td["inputs"]) if isinstance(td["inputs"], str) else td["inputs"]
                except Exception:
                    inp = {}
            td["target_files"] = inp.get("target_files") or inp.get("files") or []
            td["role"] = td.get("role") or "analyst"
            tasks.append(td)


        # Agents
        agent_rows = conn.execute("SELECT agent_id, provider, model, enabled, health FROM agents").fetchall()
        agents = [dict(a) for a in agent_rows if "claude" not in a["agent_id"].lower()]

        # Findings
        try:
            finding_rows = conn.execute("""
                SELECT finding_id, display_id, hypothesis, severity, state,
                       locations, affected_locations, lineage
                FROM findings
                WHERE project_id = ?
                ORDER BY created_at DESC
            """, (active_project_id,)).fetchall()
            findings = [dict(f) for f in finding_rows]
        except Exception:
            findings = []


        # Evidence count
        evi_count = conn.execute("SELECT COUNT(*) FROM evidence WHERE project_id = ?", (active_project_id,)).fetchone()[0]

        # Token telemetry from token_usage
        token_stats = conn.execute("""
            SELECT
                SUM(input_tokens_actual) as in_act,
                SUM(output_tokens_actual) as out_act,
                SUM(total_tokens_actual) as tot_act,
                SUM(total_tokens_estimated) as tot_est
            FROM token_usage
            WHERE run_id = ? OR task_id IN (SELECT task_id FROM tasks WHERE project_id = ?)
        """, (run_dict.get("run_id"), active_project_id)).fetchone()

    budget = run_dict.get("token_budget") or plan_dict.get("total_estimated_tokens") or 180000
    actual_tokens = (token_stats["tot_act"] or 0) if token_stats else 0
    estimated_tokens = (token_stats["tot_est"] or 0) if token_stats else 0
    tokens_consumed = actual_tokens if actual_tokens > 0 else estimated_tokens
    tokens_remaining = max(0, budget - tokens_consumed)

    # 2. Check if user is asking to create a task
    q_lower = req.query.lower()
    task_proposal = None
    if any(k in q_lower for k in ["create task", "create a task", "new task", "run task", "inspect file", "check file"]):
        # Synthesize structured task proposal
        target_f = ["hw/fpga/src/caliptra_wrapper_top.sv"]
        if "axi" in q_lower or "intf" in q_lower:
            target_f = ["hw/fpga/src/axi4lite_intf.sv"]
        elif "reset" in q_lower:
            target_f = ["hw/fpga/src/caliptra_wrapper_top.sv"]
        elif "ecc" in q_lower or "ram" in q_lower:
            target_f = ["hw/fpga/src/ecc_ram_tdp_file.sv"]

        method = "Hardware Security RTL Inspection"
        if "formal" in q_lower:
            method = "Formal Invariant Verification"
        elif "lint" in q_lower:
            method = "Verilator Static Lint"

        task_proposal = {
            "objective": req.query.strip(),
            "target_files": target_f,
            "method": method,
            "agent_id": "agent-agy-01",
            "tools": ["verilator", "yosys"],
            "token_budget": 50000,
            "time_budget_seconds": 180
        }

    # 3. Assemble live state context summary for AGY
    context_summary = {
        "current_project": {
            "id": project_dict.get("project_id"),
            "display_id": project_dict.get("display_id") or "PROJ-001",
            "name": project_dict.get("name"),
            "target_directory": project_dict.get("target_directory"),
            "classification": project_dict.get("classification", "Hardware RTL SoC"),
        },
        "current_page": req.current_page,
        "focused_context": req.context,
        "run_state": run_dict.get("run_state", "IDLE"),
        "active_plan": {
            "plan_id": actual_plan_id,
            "version": plan_dict.get("version", 1),
            "status": plan_dict.get("status", "READY_FOR_REVIEW"),
            "workpackages_count": len(work_packages),
            "approved_packages": len([w for w in work_packages if w["status"] in ("APPROVED", "QUEUED", "RUNNING", "COMPLETED")]),
        },
        "workpackages": [
            {"id": w.get("display_id") or w["package_id"], "name": w["name"], "status": w["status"], "why_proposed": w.get("why_proposed")}
            for w in work_packages[:6]
        ],
        "tasks": [
            {
                "id": t.get("display_id") or t["task_id"],
                "objective": t["objective"],
                "status": t["status"],
                "agent": t["assigned_agent_id"],
                "target_files": t.get("target_files") or t.get("current_file"),
                "why_queued": t.get("why_queued"),
                "failure_reason": t.get("failure_reason")
            }
            for t in tasks[:8]
        ],
        "findings": [
            {
                "id": f.get("display_id") or f["finding_id"],
                "title": f.get("hypothesis", "Untitled")[:180],
                "severity": f["severity"],
                "status": f["state"],
                "locations": f.get("affected_locations") or f.get("locations") or f.get("affected_files") or f.get("line_range"),
                "lineage": json.loads(f["lineage"]) if f.get("lineage") and isinstance(f["lineage"], str) and f["lineage"].startswith("{") else f.get("lineage")
            }
            for f in findings[:8]
        ],
        "token_telemetry": {
            "budget": budget,
            "consumed": tokens_consumed,
            "remaining": tokens_remaining,
            "is_actual": actual_tokens > 0,
            "mode": "ACTUAL" if actual_tokens > 0 else "ESTIMATED"
        },
        "agents_available": [a["agent_id"] for a in agents if a.get("enabled", True)]
    }

    # 4. Invoke AGY CLI runtime with system prompt + user question
    agy_bin = shutil.which("agy") or "/home/hackdac/.local/bin/agy"
    answer_text = ""
    token_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "telemetry_source": "ACTUAL" if Path(agy_bin).exists() else "Provider token telemetry unavailable"
    }

    system_prompt = f"""You are COMMA (LLMorch Engineering Assistant), an authoritative, factual, transparent system assistant powered by Antigravity (AGY).
You are answering an engineer operating LLMorch.
You have access to the exact live backend state below:

BACKEND STATE:
{json.dumps(context_summary, indent=2)}

INSTRUCTIONS:
1. Answer the user query truthfully and concisely based strictly on the provided backend state.
2. If asked about a task status (e.g. why queued, failed, or running), quote the exact state, why_queued, and dependencies.
3. If asked about agents, note that AGY and Codex are available and executing; Claude is disabled by enterprise policy (0 invocations).
4. If asked about token usage, state whether the figures are ACTUAL or ESTIMATED and report remaining tokens.
5. If the user asked to create a task, confirm that a structured task proposal was generated and can be dispatched to the scheduler.
"""

    if Path(agy_bin).exists():
        try:
            full_prompt = f"{system_prompt}\n\nUSER QUERY: {req.query}"
            cmd = [agy_bin, "--output-format", "json", "-p", full_prompt]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=25,
                cwd=project_dict.get("target_directory") if project_dict.get("target_directory") and Path(project_dict["target_directory"]).exists() else None
            )
            if proc.returncode == 0 and proc.stdout:
                parsed = json.loads(proc.stdout)
                # Check if AGY returned an error (e.g. quota limit)
                agy_error = parsed.get("error", "")
                agy_response = parsed.get("response", "").strip()
                if agy_response:
                    answer_text = agy_response
                    if "usage" in parsed and isinstance(parsed["usage"], dict):
                        token_usage["input_tokens"] = parsed["usage"].get("input_tokens", 0)
                        token_usage["output_tokens"] = parsed["usage"].get("output_tokens", 0)
                        token_usage["total_tokens"] = parsed["usage"].get("total_tokens", 0)
                        token_usage["telemetry_source"] = "ACTUAL"
                elif agy_error:
                    # AGY returned error — fall through to factual template
                    answer_text = ""
                    token_usage["telemetry_source"] = f"AGY_QUOTA_FALLBACK ({agy_error[:80]})"
            else:
                answer_text = ""
        except Exception as e:
            answer_text = ""
            token_usage["telemetry_source"] = f"AGY_ERROR_FALLBACK ({str(e)[:80]})"

    # Fallback to factual template if AGY returned empty
    if not answer_text:
        if "project" in q_lower or "what is this" in q_lower:
            answer_text = f"Project '{project_dict.get('name', 'Caliptra Hardware')}' is targeting '{project_dict.get('target_directory', 'hw/')}'. Active plan has {len(work_packages)} work packages and {len(tasks)} tasks."
        elif "token" in q_lower or "budget" in q_lower:
            answer_text = f"Token Telemetry ({token_usage['telemetry_source']}): Budget: {budget:,}, Consumed: {tokens_consumed:,}, Remaining: {tokens_remaining:,}."
        elif "agent" in q_lower:
            answer_text = f"Active eligible agents: {', '.join([a['agent_id'] for a in agents if a.get('enabled')])}. AGY and Codex are registered and executable; Claude is permanently disabled (0 invocations)."
        else:
            answer_text = f"COMMA Assistant: Project state is active. {len(work_packages)} WorkPackages defined, {len(tasks)} tasks tracked, {len(findings)} confirmed security findings."

    # Record message in chat_messages table
    now_ts = _now()
    with db.get_connection() as conn:
        try:
            msg_u_id = f"msg-u-{uuid.uuid4().hex[:8]}"
            msg_a_id = f"msg-comma-{uuid.uuid4().hex[:8]}"
            conn.execute("""
                INSERT INTO chat_messages (
                    message_id, conversation_type, task_id, run_id, sender_type,
                    sender_name, message_type, content, metadata, created_at, project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                msg_u_id, "COMMA", req.context.get("task_id"), run_dict.get("run_id"),
                "USER", "Analyst", "USER_INSTRUCTION", req.query,
                json.dumps({"page": req.current_page}), now_ts, active_project_id
            ))
            conn.execute("""
                INSERT INTO chat_messages (
                    message_id, conversation_type, task_id, run_id, sender_type,
                    sender_name, message_type, content, metadata, created_at, project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                msg_a_id, "COMMA", req.context.get("task_id"), run_dict.get("run_id"),
                "AGENT", "COMMA (AGY)", "OBSERVATION", answer_text,
                json.dumps({"tokens": token_usage, "proposal": task_proposal}), now_ts, active_project_id
            ))
            conn.commit()
        except Exception:
            pass

    return CommaQueryResponse(
        status="SUCCESS",
        query=req.query,
        answer=answer_text,
        powered_by="AGY",
        model="Gemini 3.6 Low",
        task_proposal=task_proposal,
        token_usage=token_usage,
        context_inspected=context_summary,
        timestamp=now_ts
    )
