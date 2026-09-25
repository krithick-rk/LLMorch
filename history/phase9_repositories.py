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

