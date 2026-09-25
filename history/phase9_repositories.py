"""
LLMorch Persistence - Phase 9.1 Repositories
Authoritative repository implementations for Token Usage, Budgets,
Repository Estimates, Agent Switches, Model Switches, and Analyst Configuration.
"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid

from .database import DatabaseService
from schemas.token import (
    TokenUsageRecord,
    TokenSource,
    TokenLimitStatus,
    TokenBudgetConfig,
    TokenAccountingSummary,
)
from schemas.estimation import (
    RepositoryTokenEstimate,
    LanguageTokenEstimate,
    StageTokenEstimate,
    EstimationMethod,
    ConfidenceLevel,
)
from schemas.configuration import SystemSettings
from schemas.model import Model, TokenEstimationMethod


class TokenUsageRepository:
    """Persistent storage for append-only token usage records."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, record: TokenUsageRecord) -> TokenUsageRecord:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO token_usage (
                    record_id, run_id, task_id, attempt_id, agent_id, model_id, stage,
                    input_tokens_actual, output_tokens_actual, total_tokens_actual,
                    input_tokens_estimated, output_tokens_estimated, total_tokens_estimated,
                    input_source, output_source, token_source, is_estimated,
                    token_limit, tokens_remaining, created_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.record_id,
                record.run_id,
                record.task_id,
                record.attempt_id,
                record.agent_id,
                record.model_id,
                record.stage,
                record.input_tokens_actual,
                record.output_tokens_actual,
                record.total_tokens_actual,
                record.input_tokens_estimated,
                record.output_tokens_estimated,
                record.total_tokens_estimated,
                record.input_source.value if hasattr(record.input_source, "value") else str(record.input_source),
                record.output_source.value if hasattr(record.output_source, "value") else str(record.output_source),
                record.token_source.value if hasattr(record.token_source, "value") else str(record.token_source),
                1 if record.is_estimated else 0,
                record.token_limit,
                record.tokens_remaining,
                record.created_at.isoformat(),
                record.schema_version,
            ))
            conn.commit()
        return record

    def list_records(
        self,
        run_id: Optional[str] = None,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        model_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[TokenUsageRecord]:
        where_clauses = []
        params: List[Any] = []
        if run_id:
            where_clauses.append("run_id = ?")
            params.append(run_id)
        if task_id:
            where_clauses.append("task_id = ?")
            params.append(task_id)
        if agent_id:
            where_clauses.append("agent_id = ?")
            params.append(agent_id)
        if model_id:
            where_clauses.append("model_id = ?")
            params.append(model_id)

        where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        sql = f"SELECT * FROM token_usage {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.db.get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_record(r) for r in rows]

    def _row_to_record(self, r: Any) -> TokenUsageRecord:
        return TokenUsageRecord(
            record_id=r["record_id"],
            run_id=r["run_id"],
            task_id=r["task_id"],
            attempt_id=r["attempt_id"],
            agent_id=r["agent_id"],
            model_id=r["model_id"],
            stage=r["stage"],
            input_tokens_actual=r["input_tokens_actual"],
            output_tokens_actual=r["output_tokens_actual"],
            total_tokens_actual=r["total_tokens_actual"],
            input_tokens_estimated=r["input_tokens_estimated"],
            output_tokens_estimated=r["output_tokens_estimated"],
            total_tokens_estimated=r["total_tokens_estimated"],
            input_source=TokenSource(r["input_source"]) if r["input_source"] in TokenSource._value2member_map_ else TokenSource.UNKNOWN,
            output_source=TokenSource(r["output_source"]) if r["output_source"] in TokenSource._value2member_map_ else TokenSource.UNKNOWN,
            token_source=TokenSource(r["token_source"]) if r["token_source"] in TokenSource._value2member_map_ else TokenSource.UNKNOWN,
            is_estimated=bool(r["is_estimated"]),
            token_limit=r["token_limit"],
            tokens_remaining=r["tokens_remaining"],
            created_at=datetime.fromisoformat(r["created_at"]),
            schema_version=r["schema_version"],
        )

    def get_summary(
        self,
        run_id: Optional[str] = None,
        budget: int = 500000
    ) -> TokenAccountingSummary:
        records = self.list_records(run_id=run_id, limit=5000)

        total_act = sum(r.total_tokens_actual for r in records)
        total_est = sum(r.total_tokens_estimated for r in records)
        in_act = sum(r.input_tokens_actual for r in records)
        out_act = sum(r.output_tokens_actual for r in records)
        in_est = sum(r.input_tokens_estimated for r in records)
        out_est = sum(r.output_tokens_estimated for r in records)

        effective_total = total_act if total_act > 0 else total_est
        remaining = max(0, budget - effective_total)

        pct_rem = (remaining / budget * 100.0) if budget > 0 else 0.0
        if remaining == 0 or effective_total >= budget:
            status = TokenLimitStatus.EXHAUSTED
        elif pct_rem < 10.0:
            status = TokenLimitStatus.NEAR_LIMIT
        elif pct_rem < 30.0:
            status = TokenLimitStatus.LOW
        else:
            status = TokenLimitStatus.AVAILABLE

        # Aggregates by agent
        by_agent: Dict[str, Dict[str, Any]] = {}
        for r in records:
            if r.agent_id not in by_agent:
                by_agent[r.agent_id] = {"actual": 0, "estimated": 0, "total": 0, "calls": 0}
            by_agent[r.agent_id]["actual"] += r.total_tokens_actual
            by_agent[r.agent_id]["estimated"] += r.total_tokens_estimated
            by_agent[r.agent_id]["total"] += (r.total_tokens_actual or r.total_tokens_estimated)
            by_agent[r.agent_id]["calls"] += 1

        # Aggregates by model
        by_model: Dict[str, Dict[str, Any]] = {}
        for r in records:
            if r.model_id not in by_model:
                by_model[r.model_id] = {"actual": 0, "estimated": 0, "total": 0, "calls": 0}
            by_model[r.model_id]["actual"] += r.total_tokens_actual
            by_model[r.model_id]["estimated"] += r.total_tokens_estimated
            by_model[r.model_id]["total"] += (r.total_tokens_actual or r.total_tokens_estimated)
            by_model[r.model_id]["calls"] += 1

        # Aggregates by stage
        by_stage: Dict[str, Dict[str, Any]] = {}
        for r in records:
            if r.stage not in by_stage:
                by_stage[r.stage] = {"actual": 0, "estimated": 0, "total": 0}
            by_stage[r.stage]["actual"] += r.total_tokens_actual
            by_stage[r.stage]["estimated"] += r.total_tokens_estimated
            by_stage[r.stage]["total"] += (r.total_tokens_actual or r.total_tokens_estimated)

        # Top tasks
        tasks_map: Dict[str, int] = {}
        for r in records:
            tasks_map[r.task_id] = tasks_map.get(r.task_id, 0) + (r.total_tokens_actual or r.total_tokens_estimated)
        top_tasks = [{"task_id": tid, "tokens": tok} for tid, tok in sorted(tasks_map.items(), key=lambda x: x[1], reverse=True)[:10]]

        return TokenAccountingSummary(
            total_tokens_actual=total_act,
            total_tokens_estimated=total_est,
            effective_total_tokens=effective_total,
            input_tokens_actual=in_act,
            output_tokens_actual=out_act,
            input_tokens_estimated=in_est,
            output_tokens_estimated=out_est,
            token_budget=budget,
            tokens_remaining=remaining,
            status=status,
            estimated_work_remaining=max(0, int(budget * 0.4 - effective_total)),
            by_agent=by_agent,
            by_model=by_model,
            by_stage=by_stage,
            top_tasks=top_tasks,
        )


class TokenBudgetRepository:
    """Persistent storage for configured token budgets."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save_budget(
        self,
        scope_type: str,
        scope_id: str,
        budget_limit: int,
        consumed: int = 0,
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        remaining = max(0, budget_limit - consumed)
        pct = (remaining / budget_limit * 100.0) if budget_limit > 0 else 0.0
        if remaining == 0:
            status = "EXHAUSTED"
        elif pct < 10.0:
            status = "NEAR_LIMIT"
        elif pct < 30.0:
            status = "LOW"
        else:
            status = "AVAILABLE"

        budget_id = f"bgt-{scope_type}-{scope_id}"
        now = datetime.now(timezone.utc).isoformat()

        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO token_budgets (
                    budget_id, run_id, scope_type, scope_id, budget_limit,
                    consumed, remaining, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (budget_id, run_id, scope_type, scope_id, budget_limit, consumed, remaining, status, now))
            conn.commit()

        return {
            "budget_id": budget_id,
            "run_id": run_id,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "budget_limit": budget_limit,
            "consumed": consumed,
            "remaining": remaining,
            "status": status,
            "updated_at": now,
        }

    def get_budget(self, scope_type: str, scope_id: str) -> Optional[Dict[str, Any]]:
        budget_id = f"bgt-{scope_type}-{scope_id}"
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM token_budgets WHERE budget_id = ?", (budget_id,)).fetchone()
            return dict(row) if row else None

    def list_budgets(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            if run_id:
                rows = conn.execute("SELECT * FROM token_budgets WHERE run_id = ?", (run_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM token_budgets").fetchall()
            return [dict(r) for r in rows]


class RepositoryEstimateRepository:
    """Persistent storage for repository token estimates."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, est: RepositoryTokenEstimate) -> RepositoryTokenEstimate:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO repository_token_estimates (
                    estimate_id, repository_path, snapshot_id, total_files, source_files,
                    security_relevant_files, excluded_files, raw_tokens, llm_scoped_tokens,
                    analysis_unit_tokens, context_expansion_tokens, initial_analysis_tokens,
                    followup_tokens, estimated_total, recommended_budget, estimation_method,
                    confidence, breakdown_by_language, breakdown_by_stage, created_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                est.estimate_id,
                est.repository_path,
                est.snapshot_id,
                est.total_files_discovered,
                est.source_files_count,
                est.security_relevant_files_count,
                est.excluded_files_count,
                est.raw_token_estimate,
                est.llm_scoped_token_estimate,
                est.analysis_unit_estimate,
                est.context_expansion_estimate,
                est.initial_analysis_estimate,
                est.followup_analysis_estimate,
                est.estimated_total_tokens,
                est.recommended_budget,
                est.estimation_method.value,
                est.confidence.value,
                json.dumps([l.model_dump() for l in est.breakdown_by_language]),
                json.dumps([s.model_dump() for s in est.breakdown_by_stage]),
                est.created_at.isoformat(),
                est.schema_version,
            ))
            conn.commit()
        return est

    def get(self, estimate_id: str) -> Optional[RepositoryTokenEstimate]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM repository_token_estimates WHERE estimate_id = ?", (estimate_id,)).fetchone()
            if not row:
                return None
            return self._row_to_est(row)

    def get_latest_for_repo(self, repo_path: str) -> Optional[RepositoryTokenEstimate]:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM repository_token_estimates WHERE repository_path = ? ORDER BY created_at DESC LIMIT 1",
                (repo_path,)
            ).fetchone()
            return self._row_to_est(row) if row else None

    def _row_to_est(self, r: Any) -> RepositoryTokenEstimate:
        lang_data = json.loads(r["breakdown_by_language"]) if r["breakdown_by_language"] else []
        stage_data = json.loads(r["breakdown_by_stage"]) if r["breakdown_by_stage"] else []
        return RepositoryTokenEstimate(
            estimate_id=r["estimate_id"],
            repository_path=r["repository_path"],
            snapshot_id=r["snapshot_id"],
            total_files_discovered=r["total_files"],
            source_files_count=r["source_files"],
            security_relevant_files_count=r["security_relevant_files"],
            excluded_files_count=r["excluded_files"],
            raw_token_estimate=r["raw_tokens"],
            llm_scoped_token_estimate=r["llm_scoped_tokens"],
            analysis_unit_estimate=r["analysis_unit_tokens"],
            context_expansion_estimate=r["context_expansion_tokens"],
            initial_analysis_estimate=r["initial_analysis_tokens"],
            followup_analysis_estimate=r["followup_tokens"],
            estimated_total_tokens=r["estimated_total"],
            recommended_budget=r["recommended_budget"],
            estimation_method=EstimationMethod(r["estimation_method"]),
            confidence=ConfidenceLevel(r["confidence"]),
            breakdown_by_language=[LanguageTokenEstimate(**l) for l in lang_data],
            breakdown_by_stage=[StageTokenEstimate(**s) for s in stage_data],
            created_at=datetime.fromisoformat(r["created_at"]),
            schema_version=r["schema_version"],
        )


class AgentSwitchRepository:
    """Persistent audit log of agent switches and failovers."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def record_switch(
        self,
        task_id: str,
        run_id: str,
        previous_agent_id: str,
        new_agent_id: str,
        reason: str,
        switch_type: str = "MANUAL",
        previous_model_id: Optional[str] = None,
        new_model_id: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
        resume_action: str = "RESUME"
    ) -> Dict[str, Any]:
        switch_id = f"sw-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO agent_switches (
                    switch_id, task_id, run_id, previous_agent_id, new_agent_id,
                    previous_model_id, new_model_id, switch_type, reason,
                    checkpoint_id, resume_action, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                switch_id, task_id, run_id, previous_agent_id, new_agent_id,
                previous_model_id, new_model_id, switch_type, reason,
                checkpoint_id, resume_action, "COMPLETED", now
            ))
            conn.commit()
        return {
            "switch_id": switch_id,
            "task_id": task_id,
            "run_id": run_id,
            "previous_agent_id": previous_agent_id,
            "new_agent_id": new_agent_id,
            "previous_model_id": previous_model_id,
            "new_model_id": new_model_id,
            "switch_type": switch_type,
            "reason": reason,
            "checkpoint_id": checkpoint_id,
            "resume_action": resume_action,
            "status": "COMPLETED",
            "created_at": now,
        }

    def list_switches(
        self,
        task_id: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        where = []
        params = []
        if task_id:
            where.append("task_id = ?")
            params.append(task_id)
        if run_id:
            where.append("run_id = ?")
            params.append(run_id)

        w_str = ("WHERE " + " AND ".join(where)) if where else ""
        sql = f"SELECT * FROM agent_switches {w_str} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self.db.get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]


class ModelSwitchRepository:
    """Persistent audit log of model switches."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def record_switch(
        self,
        agent_id: str,
        previous_model_id: str,
        new_model_id: str,
        reason: str,
        task_id: Optional[str] = None,
        run_id: Optional[str] = None,
        scope: str = "CURRENT_TASK"
    ) -> Dict[str, Any]:
        switch_id = f"msw-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO model_switches (
                    switch_id, task_id, run_id, agent_id, previous_model_id,
                    new_model_id, reason, scope, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (switch_id, task_id, run_id, agent_id, previous_model_id, new_model_id, reason, scope, now))
            conn.commit()
        return {
            "switch_id": switch_id,
            "task_id": task_id,
            "run_id": run_id,
            "agent_id": agent_id,
            "previous_model_id": previous_model_id,
            "new_model_id": new_model_id,
            "reason": reason,
            "scope": scope,
            "created_at": now,
        }

    def list_switches(
        self,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        where = []
        params = []
        if agent_id:
            where.append("agent_id = ?")
            params.append(agent_id)
        if task_id:
            where.append("task_id = ?")
            params.append(task_id)

        w_str = ("WHERE " + " AND ".join(where)) if where else ""
        sql = f"SELECT * FROM model_switches {w_str} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self.db.get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]


class ConfigurationRepository:
    """Persistent storage for analyst configurations."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save_settings(self, settings: SystemSettings, updated_by: str = "analyst") -> SystemSettings:
        now = datetime.now(timezone.utc).isoformat()
        payload = settings.model_dump_json()
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO configuration_records (
                    key, value, category, updated_at, updated_by
                ) VALUES (?, ?, ?, ?, ?)
            """, ("system_settings", payload, "global", now, updated_by))
            conn.commit()
        return settings

    def get_settings(self) -> SystemSettings:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM configuration_records WHERE key = ?", ("system_settings",)
            ).fetchone()
            if row and row["value"]:
                try:
                    data = json.loads(row["value"])
                    return SystemSettings(**data)
                except Exception:
                    pass
        default_settings = SystemSettings()
        self.save_settings(default_settings, updated_by="system")
        return default_settings


class TargetRepositoryRepository:
    """Persistent storage for authoritative target and recent attack repositories."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(
        self,
        repo_data: Optional[Dict[str, Any]] = None,
        *,
        repository_path: Optional[str] = None,
        repository_name: Optional[str] = None,
        repository_family: str = "UNKNOWN",
        git_revision: Optional[str] = None,
        is_git: bool = False,
        file_count: int = 0,
        languages: Optional[List[str]] = None,
        snapshot_id: Optional[str] = None,
        is_current: bool = False,
        last_used: Optional[str] = None,
        created_at: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        data = dict(repo_data or {})
        if repository_path is not None:
            data["repository_path"] = repository_path
        if repository_name is not None:
            data["repository_name"] = repository_name
        if repository_family != "UNKNOWN" or "repository_family" not in data:
            data["repository_family"] = repository_family
        if git_revision is not None:
            data["git_revision"] = git_revision
        if is_git or "is_git" not in data:
            data["is_git"] = is_git
        if file_count != 0 or "file_count" not in data:
            data["file_count"] = file_count
        if languages is not None:
            data["languages"] = languages
        if snapshot_id is not None:
            data["snapshot_id"] = snapshot_id
        if is_current or "is_current" not in data:
            data["is_current"] = is_current
        if last_used is not None:
            data["last_used"] = last_used
        if created_at is not None:
            data["created_at"] = created_at
        data.update(kwargs)

        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            if data.get("is_current"):
                conn.execute("UPDATE target_repositories SET is_current = 0")
            conn.execute("""
                INSERT OR REPLACE INTO target_repositories (
                    repository_path, repository_name, repository_family, git_revision,
                    is_git, file_count, languages, snapshot_id, is_current, last_used, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["repository_path"],
                data["repository_name"],
                data.get("repository_family", "UNKNOWN"),
                data.get("git_revision"),
                1 if data.get("is_git") else 0,
                data.get("file_count", 0),
                json.dumps(data.get("languages", [])),
                data.get("snapshot_id"),
                1 if data.get("is_current") else 0,
                data.get("last_used", now),
                data.get("created_at", now),
            ))
            conn.commit()
        return data

    def set_current(self, repo_path: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("UPDATE target_repositories SET is_current = 0")
            conn.execute("""
                UPDATE target_repositories
                SET is_current = 1, last_used = ?
                WHERE repository_path = ?
            """, (now, repo_path))
            conn.commit()

    def get_current(self) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM target_repositories WHERE is_current = 1 LIMIT 1").fetchone()
            if row:
                d = dict(row)
                d["languages"] = json.loads(d["languages"]) if d.get("languages") else []
                d["is_git"] = bool(d.get("is_git"))
                return d
            return None

    def list_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        import os
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM target_repositories ORDER BY last_used DESC LIMIT ?", (limit,)).fetchall()
            items = []
            for r in rows:
                d = dict(r)
                d["languages"] = json.loads(d["languages"]) if d.get("languages") else []
                d["is_git"] = bool(d.get("is_git"))
                d["available"] = os.path.exists(d["repository_path"]) and os.path.isdir(d["repository_path"])
                items.append(d)
            return items


class AnalystInstructionRepository:
    """Persistent storage for analyst instructions."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        inst_id = data.get("instruction_id") or f"inst-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO analyst_instructions (
                    instruction_id, run_id, task_id, attempt_id, agent_id, role,
                    message, scope, requested_action, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                inst_id,
                data.get("run_id"),
                data["task_id"],
                data.get("attempt_id", 1),
                data.get("agent_id"),
                data.get("role"),
                data["message"],
                data.get("scope"),
                data.get("requested_action", "RE_EXECUTE"),
                data.get("created_by", "analyst"),
                data.get("created_at") or now,
            ))
            conn.commit()
        data["instruction_id"] = inst_id
        data["created_at"] = data.get("created_at") or now
        return data

    def get(self, instruction_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM analyst_instructions WHERE instruction_id = ?",
                (instruction_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_for_task(self, task_id: str) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM analyst_instructions WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,),
            ).fetchall()
            return [dict(r) for r in rows]


class TaskAttemptRepository:
    """Persistent storage for task attempt lineage."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def create_attempt(
        self,
        task_id: str,
        agent_id: str,
        model_id: Optional[str] = None,
        role: str = "general_analysis",
        instruction_id: Optional[str] = None,
        parent_attempt_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        run_id: Optional[str] = None,
        approach: Optional[str] = None,
        hypothesis: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.db.get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM task_attempts WHERE task_id = ?",
                (task_id,),
            ).fetchone()[0]
            attempt_number = count + 1
            attempt_id = f"{task_id}-attempt-{attempt_number}"
            now = datetime.now(timezone.utc).isoformat()

            conn.execute("""
                INSERT INTO task_attempts (
                    attempt_id, task_id, attempt_number, run_id, parent_run_id,
                    parent_attempt_id, agent_id, model_id, role, instruction_id,
                    status, approach, hypothesis, evidence_ids, tool_execution_ids,
                    finding_ids, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                attempt_id, task_id, attempt_number, run_id, parent_run_id,
                parent_attempt_id, agent_id, model_id, role, instruction_id,
                "RUNNING", approach, hypothesis, json.dumps([]), json.dumps([]),
                json.dumps([]), now, None
            ))
            # Update tasks current_attempt and retry_count
            conn.execute("""
                UPDATE tasks
                SET current_attempt = ?, retry_count = ?, assigned_agent_id = ?
                WHERE task_id = ?
            """, (attempt_number, max(0, attempt_number - 1), agent_id, task_id))
            conn.commit()

        return {
            "attempt_id": attempt_id,
            "task_id": task_id,
            "attempt_number": attempt_number,
            "run_id": run_id,
            "parent_run_id": parent_run_id,
            "parent_attempt_id": parent_attempt_id,
            "agent_id": agent_id,
            "model_id": model_id,
            "role": role,
            "instruction_id": instruction_id,
            "status": "RUNNING",
            "approach": approach,
            "hypothesis": hypothesis,
            "evidence_ids": [],
            "tool_execution_ids": [],
            "finding_ids": [],
            "created_at": now,
        }

    def list_for_task(self, task_id: str) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM task_attempts WHERE task_id = ? ORDER BY attempt_number ASC",
                (task_id,),
            ).fetchall()
            items = []
            for r in rows:
                d = dict(r)
                d["evidence_ids"] = json.loads(d["evidence_ids"]) if d.get("evidence_ids") else []
                d["tool_execution_ids"] = json.loads(d["tool_execution_ids"]) if d.get("tool_execution_ids") else []
                d["finding_ids"] = json.loads(d["finding_ids"]) if d.get("finding_ids") else []
                items.append(d)
            return items

    def update_attempt(self, attempt_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            sets = []
            vals = []
            for k, v in kwargs.items():
                if isinstance(v, (list, dict)):
                    v = json.dumps(v)
                sets.append(f"{k} = ?")
                vals.append(v)
            if not sets:
                return None
            vals.append(attempt_id)
            conn.execute(f"UPDATE task_attempts SET {', '.join(sets)} WHERE attempt_id = ?", vals)
            conn.commit()
            row = conn.execute("SELECT * FROM task_attempts WHERE attempt_id = ?", (attempt_id,)).fetchone()
            if row:
                d = dict(row)
                d["evidence_ids"] = json.loads(d["evidence_ids"]) if d.get("evidence_ids") else []
                d["tool_execution_ids"] = json.loads(d["tool_execution_ids"]) if d.get("tool_execution_ids") else []
                d["finding_ids"] = json.loads(d["finding_ids"]) if d.get("finding_ids") else []
                return d
            return None


class ToolExecutionRepository:
    """Persistent storage for tool executions and evidence links."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def record_execution(self, data: Dict[str, Any]) -> Dict[str, Any]:
        exec_id = data.get("execution_id") or f"exec-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        args = data.get("args") or []
        if isinstance(args, list):
            args_json = json.dumps(args)
        else:
            args_json = str(args)

        ev_ids = data.get("evidence_ids") or []
        if isinstance(ev_ids, list):
            ev_json = json.dumps(ev_ids)
        else:
            ev_json = str(ev_ids)

        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO tool_executions (
                    execution_id, tool_name, category, agent_id, task_id, run_id,
                    command, args, working_dir, status, exit_code, stdout_artifact,
                    stderr_artifact, execution_result, evidence_ids, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exec_id,
                data["tool_name"],
                data.get("category", "GENERAL"),
                data.get("agent_id"),
                data.get("task_id"),
                data.get("run_id"),
                data["command"],
                args_json,
                data.get("working_dir"),
                data.get("status", "COMPLETED"),
                data.get("exit_code", 0),
                data.get("stdout_artifact"),
                data.get("stderr_artifact"),
                data.get("execution_result"),
                ev_json,
                data.get("started_at") or now,
                data.get("completed_at") or now,
            ))
            conn.commit()

        data["execution_id"] = exec_id
        data["started_at"] = data.get("started_at") or now
        data["completed_at"] = data.get("completed_at") or now
        return data

    def list_executions(
        self,
        tool_name: Optional[str] = None,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            filters = []
            params = []
            if tool_name:
                filters.append("tool_name = ?")
                params.append(tool_name)
            if task_id:
                filters.append("task_id = ?")
                params.append(task_id)
            if agent_id:
                filters.append("agent_id = ?")
                params.append(agent_id)
            where = ("WHERE " + " AND ".join(filters)) if filters else ""
            rows = conn.execute(
                f"SELECT * FROM tool_executions {where} ORDER BY started_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()
            items = []
            for r in rows:
                d = dict(r)
                d["args"] = json.loads(d["args"]) if d.get("args") else []
                d["evidence_ids"] = json.loads(d["evidence_ids"]) if d.get("evidence_ids") else []
                items.append(d)
            return items

    def list_for_task(self, task_id: str) -> List[Dict[str, Any]]:
        return self.list_executions(task_id=task_id)


class AgentRoleRepository:
    """Manages task-scoped and default agent roles."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def assign_role(
        self,
        agent_id: str,
        role: str,
        task_id: Optional[str] = None,
        assigned_by: str = "analyst",
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        asgn_id = f"asgn-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO agent_role_assignments (
                    assignment_id, agent_id, task_id, role, assigned_by, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (asgn_id, agent_id, task_id, role, assigned_by, reason, now))
            # If not task-specific, or updating active agent role in agents table:
            conn.execute("UPDATE agents SET role = ? WHERE agent_id = ?", (role, agent_id))
            if task_id:
                conn.execute("UPDATE tasks SET role = ? WHERE task_id = ?", (role, task_id))
            conn.commit()

        return {
            "assignment_id": asgn_id,
            "agent_id": agent_id,
            "task_id": task_id,
            "role": role,
            "assigned_by": assigned_by,
            "reason": reason,
            "created_at": now,
        }

    def get_role(self, agent_id: str, task_id: Optional[str] = None) -> str:
        with self.db.get_connection() as conn:
            if task_id:
                row = conn.execute(
                    "SELECT role FROM agent_role_assignments WHERE agent_id = ? AND task_id = ? ORDER BY created_at DESC LIMIT 1",
                    (agent_id, task_id)
                ).fetchone()
                if row and row[0]:
                    return row[0]
            row = conn.execute("SELECT role FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
            return row[0] if (row and row[0]) else "general_analysis"


class ReproducerVersionRepository:
    """Tracks versions and execution lineage of PoC reproducers."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save_version(
        self,
        finding_id: str,
        reproducer_type: str,
        language: str,
        code_content: str,
        location: Optional[str] = None,
        status: str = "DRAFT",
        sandbox_mode: str = "rootless-container",
        execution_command: Optional[str] = None,
        execution_result: Optional[str] = None,
        observed_behavior: Optional[str] = None,
        determinism: Optional[str] = None,
        evidence_id: Optional[str] = None,
        instruction_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.db.get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM reproducer_versions WHERE finding_id = ?",
                (finding_id,),
            ).fetchone()[0]
            version_number = count + 1
            version_id = f"{finding_id}-poc-v{version_number}"
            now = datetime.now(timezone.utc).isoformat()

            conn.execute("""
                INSERT INTO reproducer_versions (
                    version_id, finding_id, version_number, reproducer_type, language,
                    location, code_content, status, sandbox_mode, execution_command,
                    execution_result, observed_behavior, determinism, evidence_id,
                    instruction_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                version_id, finding_id, version_number, reproducer_type, language,
                location or f"reproducers/{finding_id}_v{version_number}.{language.lower()}",
                code_content, status, sandbox_mode, execution_command,
                execution_result, observed_behavior, determinism, evidence_id,
                instruction_id, now
            ))
            # Sync findings reproducer_state
            conn.execute(
                "UPDATE findings SET reproducer_state = ? WHERE finding_id = ?",
                (status, finding_id)
            )
            conn.commit()

        return {
            "version_id": version_id,
            "finding_id": finding_id,
            "version_number": version_number,
            "reproducer_type": reproducer_type,
            "language": language,
            "location": location,
            "code_content": code_content,
            "status": status,
            "sandbox_mode": sandbox_mode,
            "execution_command": execution_command,
            "execution_result": execution_result,
            "observed_behavior": observed_behavior,
            "determinism": determinism,
            "evidence_id": evidence_id,
            "instruction_id": instruction_id,
            "created_at": now,
        }

    def list_versions(self, finding_id: str) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM reproducer_versions WHERE finding_id = ? ORDER BY version_number ASC",
                (finding_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_version(self, version_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            sets = []
            vals = []
            for k, v in kwargs.items():
                sets.append(f"{k} = ?")
                vals.append(v)
            if not sets:
                return None
            vals.append(version_id)
            conn.execute(f"UPDATE reproducer_versions SET {', '.join(sets)} WHERE version_id = ?", vals)
            conn.commit()
            row = conn.execute("SELECT * FROM reproducer_versions WHERE version_id = ?", (version_id,)).fetchone()
            return dict(row) if row else None


class QuestionRepository:
    """Persistent storage for analyst questions and human-in-the-loop decisions."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def create_question(
        self,
        reason: str,
        question: str,
        options: List[Dict[str, Any]],
        run_id: Optional[str] = None,
        task_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        default_option: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        question_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        qid = question_id or f"q-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        opts_json = json.dumps(options)
        ctx_json = json.dumps(context or {})

        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO questions (
                    question_id, run_id, task_id, attempt_id, agent_id,
                    status, reason, question, options, default_option,
                    created_at, answered_at, answer, analyst_id, context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                qid, run_id, task_id, attempt_id, agent_id,
                "QUESTION_PENDING", reason, question, opts_json, default_option,
                now, None, None, "analyst", ctx_json
            ))
            conn.commit()

        return {
            "question_id": qid,
            "run_id": run_id,
            "task_id": task_id,
            "attempt_id": attempt_id,
            "agent_id": agent_id,
            "status": "QUESTION_PENDING",
            "reason": reason,
            "question": question,
            "options": options,
            "default_option": default_option,
            "created_at": now,
            "answered_at": None,
            "answer": None,
            "analyst_id": "analyst",
            "context": context or {},
        }

    def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM questions WHERE question_id = ?", (question_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["options"] = json.loads(d["options"]) if isinstance(d.get("options"), str) else (d.get("options") or [])
            d["context"] = json.loads(d["context"]) if isinstance(d.get("context"), str) else (d.get("context") or {})
            return d

    def list_questions(
        self,
        run_id: Optional[str] = None,
        task_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            filters = []
            params = []
            if run_id:
                filters.append("run_id = ?")
                params.append(run_id)
            if task_id:
                filters.append("task_id = ?")
                params.append(task_id)
            if status:
                filters.append("status = ?")
                params.append(status)
            where = ("WHERE " + " AND ".join(filters)) if filters else ""
            query = f"SELECT * FROM questions {where} ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["options"] = json.loads(d["options"]) if isinstance(d.get("options"), str) else (d.get("options") or [])
                d["context"] = json.loads(d["context"]) if isinstance(d.get("context"), str) else (d.get("context") or {})
                results.append(d)
            return results

    def answer_question(self, question_id: str, answer: str, analyst_id: str = "analyst") -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE questions
                SET status = 'QUESTION_ANSWERED', answered_at = ?, answer = ?, analyst_id = ?
                WHERE question_id = ?
            """, (now, answer, analyst_id, question_id))
            conn.commit()
        return self.get_question(question_id)

    def dismiss_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE questions
                SET status = 'QUESTION_DISMISSED', answered_at = ?
                WHERE question_id = ?
            """, (now, question_id))
            conn.commit()
        return self.get_question(question_id)


