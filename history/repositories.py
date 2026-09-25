"""
LLMorch Persistence - Repositories
Repository abstractions for CRUD operations across task, run, agent, event, checkpoint, artifact, evidence, finding, memory, and Phase 7 repository intelligence models.
"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from .database import DatabaseService
from schemas.task import Task
from schemas.run import Run
from schemas.agent import Agent
from schemas.event import Event, EventType
from schemas.checkpoint import Checkpoint
from schemas.artifact import Artifact
from schemas.evidence import Evidence
from schemas.finding import Finding
from schemas.analysis_unit import AnalysisUnit, AnalysisUnitType, PriorityLevel
from schemas.security_surface import SecuritySurface, AttackerCapability, TrustBoundary, EntryPoint, SecurityAsset, Countermeasure
from schemas.file_classification import FileClassificationType, FileClassificationRecord, SymlinkRecord, SymlinkStatus
from schemas.repository_intelligence import (
    ExtendedRepositorySnapshot,
    BuildTarget,
    SymbolEntity,
    DependencyRelation,
    DependencyType,
    ReachabilityStatus,
    HW_SW_Contract,
    SecretQuarantineRecord,
    ContextExpansionRecord,
)
from schemas.memory import (
    PatternRecord,
    ProjectMemoryRecord,
    ResearchStrategyRecord,
    ResearchOutcomeRecord,
    MemoryPromotionRecord,
    PatternDomain,
    MemoryConfidence,
    MemoryPrivacyClass,
)


class TaskRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, task: Task) -> Task:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO tasks (
                    task_id, workflow_id, parent_task_id, objective, inputs, dependencies,
                    required_capabilities, preferred_roles, risk_level, workspace_policy,
                    tool_policy, budget, status, assigned_agent_id, retry_count,
                    acceptance_criteria, result_ref, schema_version, created_at, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    workflow_id=excluded.workflow_id,
                    parent_task_id=excluded.parent_task_id,
                    objective=excluded.objective,
                    inputs=excluded.inputs,
                    dependencies=excluded.dependencies,
                    required_capabilities=excluded.required_capabilities,
                    preferred_roles=excluded.preferred_roles,
                    risk_level=excluded.risk_level,
                    workspace_policy=excluded.workspace_policy,
                    tool_policy=excluded.tool_policy,
                    budget=excluded.budget,
                    status=excluded.status,
                    assigned_agent_id=excluded.assigned_agent_id,
                    retry_count=excluded.retry_count,
                    acceptance_criteria=excluded.acceptance_criteria,
                    result_ref=excluded.result_ref,
                    schema_version=excluded.schema_version,
                    created_at=excluded.created_at,
                    started_at=excluded.started_at,
                    completed_at=excluded.completed_at
            """, (
                task.task_id,
                task.workflow_id,
                task.parent_task_id,
                task.objective,
                json.dumps(task.inputs),
                json.dumps(task.dependencies),
                json.dumps(task.required_capabilities),
                json.dumps(task.preferred_roles),
                task.risk_level.value,
                task.workspace_policy.model_dump_json(),
                task.tool_policy.model_dump_json(),
                task.budget.model_dump_json(),
                task.status.value,
                task.assigned_agent_id,
                task.retry_count,
                json.dumps(task.acceptance_criteria),
                task.result_ref,
                task.schema_version,
                task.created_at.isoformat(),
                task.started_at.isoformat() if task.started_at else None,
                task.completed_at.isoformat() if task.completed_at else None,
            ))
            conn.commit()
        return task

    def get(self, task_id: str) -> Optional[Task]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not row:
                return None
            return Task(
                task_id=row["task_id"],
                workflow_id=row["workflow_id"],
                parent_task_id=row["parent_task_id"],
                objective=row["objective"],
                inputs=json.loads(row["inputs"]),
                dependencies=json.loads(row["dependencies"]),
                required_capabilities=json.loads(row["required_capabilities"]),
                preferred_roles=json.loads(row["preferred_roles"]),
                risk_level=row["risk_level"],
                workspace_policy=json.loads(row["workspace_policy"]),
                tool_policy=json.loads(row["tool_policy"]),
                budget=json.loads(row["budget"]),
                status=row["status"],
                assigned_agent_id=row["assigned_agent_id"],
                retry_count=row["retry_count"],
                acceptance_criteria=json.loads(row["acceptance_criteria"]),
                result_ref=row["result_ref"],
                schema_version=row["schema_version"],
                created_at=datetime.fromisoformat(row["created_at"]),
                started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            )


class AgentRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, agent: Agent) -> Agent:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO agents (
                    agent_id, provider, interface, model, capabilities, protocols,
                    permissions, health, availability, concurrency_limit, usage_status,
                    quota_status, workspace_class, auth_profile, adapter_version, metadata, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                agent.agent_id,
                agent.provider,
                agent.interface.value,
                agent.model,
                json.dumps(agent.capabilities),
                json.dumps(agent.protocols),
                json.dumps(agent.permissions),
                agent.health.value,
                1 if agent.availability else 0,
                agent.concurrency_limit,
                agent.usage_status.model_dump_json(),
                agent.quota_status.value,
                agent.workspace_class,
                json.dumps(agent.auth_profile),
                agent.adapter_version,
                json.dumps(agent.metadata),
                agent.schema_version,
            ))
            conn.commit()
        return agent

    def get(self, agent_id: str) -> Optional[Agent]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
            if not row:
                return None
            return Agent(
                agent_id=row["agent_id"],
                provider=row["provider"],
                interface=row["interface"],
                model=row["model"],
                capabilities=json.loads(row["capabilities"]),
                protocols=json.loads(row["protocols"]),
                permissions=json.loads(row["permissions"]),
                health=row["health"],
                availability=bool(row["availability"]),
                concurrency_limit=row["concurrency_limit"],
                usage_status=json.loads(row["usage_status"]),
                quota_status=row["quota_status"],
                workspace_class=row["workspace_class"],
                auth_profile=json.loads(row["auth_profile"]),
                adapter_version=row["adapter_version"],
                metadata=json.loads(row["metadata"]),
                schema_version=row["schema_version"],
            )


class RunRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, run: Run) -> Run:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO runs (
                    run_id, task_id, parent_run_id, agent_id, adapter_version, start_time, end_time,
                    process_id, exit_status, workspace_id, environment_fingerprint,
                    status, failure_code, failure_reason, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run.run_id,
                run.task_id,
                run.parent_run_id,
                run.agent_id,
                run.adapter_version,
                run.start_time.isoformat(),
                run.end_time.isoformat() if run.end_time else None,
                run.process_id,
                run.exit_status,
                run.workspace_id,
                run.environment_fingerprint,
                run.status.value,
                run.failure_code,
                run.failure_reason,
                run.schema_version,
            ))
            conn.commit()
        return run

    def _row_to_run(self, row) -> Run:
        return Run(
            run_id=row["run_id"],
            task_id=row["task_id"],
            parent_run_id=row["parent_run_id"],
            agent_id=row["agent_id"],
            adapter_version=row["adapter_version"],
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            process_id=row["process_id"],
            exit_status=row["exit_status"],
            workspace_id=row["workspace_id"],
            environment_fingerprint=row["environment_fingerprint"],
            status=row["status"],
            failure_code=row["failure_code"],
            failure_reason=row["failure_reason"],
            schema_version=row["schema_version"],
        )

    def get(self, run_id: str) -> Optional[Run]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return None
            return self._row_to_run(row)

    def list_for_task(self, task_id: str) -> List[Run]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM runs WHERE task_id = ? ORDER BY start_time ASC", (task_id,)).fetchall()
            return [self._row_to_run(r) for r in rows]

    def list_all(self) -> List[Run]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM runs ORDER BY start_time ASC").fetchall()
            return [self._row_to_run(r) for r in rows]


class CheckpointRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, checkpoint: Checkpoint) -> Checkpoint:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO checkpoints (
                    checkpoint_id, task_id, workflow_id, run_id, completed_subtasks,
                    remaining_subtasks, task_state, artifact_refs, evidence_refs,
                    finding_refs, hypothesis_refs, workspace_snapshot, repository_snapshot,
                    next_action, recovery_context, is_valid, invalidation_reason, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                checkpoint.checkpoint_id,
                checkpoint.task_id,
                checkpoint.workflow_id,
                checkpoint.run_id,
                json.dumps(checkpoint.completed_subtasks),
                json.dumps(checkpoint.remaining_subtasks),
                json.dumps(checkpoint.task_state),
                json.dumps(checkpoint.artifact_refs),
                json.dumps(checkpoint.evidence_refs),
                json.dumps(checkpoint.finding_refs),
                json.dumps(checkpoint.hypothesis_refs),
                json.dumps(checkpoint.workspace_snapshot),
                json.dumps(checkpoint.repository_snapshot),
                checkpoint.next_action,
                json.dumps(checkpoint.recovery_context),
                1 if checkpoint.is_valid else 0,
                checkpoint.invalidation_reason,
                checkpoint.schema_version,
                checkpoint.created_at.isoformat(),
            ))
            conn.commit()
        return checkpoint

    def _row_to_checkpoint(self, row) -> Checkpoint:
        return Checkpoint(
            checkpoint_id=row["checkpoint_id"],
            task_id=row["task_id"],
            workflow_id=row["workflow_id"],
            run_id=row["run_id"],
            completed_subtasks=json.loads(row["completed_subtasks"]) if row["completed_subtasks"] else [],
            remaining_subtasks=json.loads(row["remaining_subtasks"]) if row["remaining_subtasks"] else [],
            task_state=json.loads(row["task_state"]) if row["task_state"] else {},
            artifact_refs=json.loads(row["artifact_refs"]) if row["artifact_refs"] else [],
            evidence_refs=json.loads(row["evidence_refs"]) if row["evidence_refs"] else [],
            finding_refs=json.loads(row["finding_refs"]) if row["finding_refs"] else [],
            hypothesis_refs=json.loads(row["hypothesis_refs"]) if row["hypothesis_refs"] else [],
            workspace_snapshot=json.loads(row["workspace_snapshot"]) if row["workspace_snapshot"] else {},
            repository_snapshot=json.loads(row["repository_snapshot"]) if row["repository_snapshot"] else {},
            next_action=row["next_action"],
            recovery_context=json.loads(row["recovery_context"]) if row["recovery_context"] else {},
            is_valid=bool(row["is_valid"]),
            invalidation_reason=row["invalidation_reason"],
            schema_version=row["schema_version"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def get(self, checkpoint_id: str) -> Optional[Checkpoint]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)).fetchone()
            return self._row_to_checkpoint(row) if row else None

    def list_for_task(self, task_id: str) -> List[Checkpoint]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM checkpoints WHERE task_id = ? ORDER BY created_at ASC", (task_id,)).fetchall()
            return [self._row_to_checkpoint(r) for r in rows]

    def get_latest_for_task(self, task_id: str) -> Optional[Checkpoint]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM checkpoints WHERE task_id = ? ORDER BY created_at DESC LIMIT 1", (task_id,)).fetchone()
            return self._row_to_checkpoint(row) if row else None


class EventRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def record(self, event: Event) -> Event:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO events (
                    event_id, run_id, timestamp, event_type, actor, tool,
                    payload_ref, payload, parent_event_id, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id,
                event.run_id,
                event.timestamp.isoformat(),
                event.event_type.value,
                event.actor,
                event.tool,
                event.payload_ref,
                json.dumps(event.payload or {}),
                event.parent_event_id,
                event.schema_version,
            ))
            conn.commit()
        return event

    def _row_to_event(self, row) -> Event:
        return Event(
            event_id=row["event_id"],
            run_id=row["run_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            event_type=EventType(row["event_type"]),
            actor=row["actor"],
            tool=row["tool"],
            payload_ref=row["payload_ref"],
            payload=json.loads(row["payload"]) if row["payload"] else {},
            parent_event_id=row["parent_event_id"],
            schema_version=row["schema_version"],
        )

    def list_for_run(self, run_id: str) -> List[Event]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM events WHERE run_id = ? ORDER BY timestamp ASC", (run_id,)).fetchall()
            return [self._row_to_event(r) for r in rows]

    def list_all(self) -> List[Event]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM events ORDER BY timestamp ASC").fetchall()
            return [self._row_to_event(r) for r in rows]


# Phase 6 Repositories
class ProjectMemoryRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, rec: ProjectMemoryRecord) -> ProjectMemoryRecord:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO project_memory (
                    record_id, project_id, task_id, run_id, domain,
                    architecture_facts, local_findings, rejected_hypotheses,
                    successful_strategies, failed_strategies, evidence_refs,
                    privacy_class, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rec.record_id,
                rec.project_id,
                rec.task_id,
                rec.run_id,
                rec.domain.value,
                json.dumps(rec.architecture_facts, default=str),
                json.dumps(rec.local_findings, default=str),
                json.dumps(rec.rejected_hypotheses, default=str),
                json.dumps(rec.successful_strategies, default=str),
                json.dumps(rec.failed_strategies, default=str),
                json.dumps(rec.evidence_refs, default=str),
                rec.privacy_class.value,
                rec.created_at.isoformat(),
            ))
            conn.commit()
        return rec

    def list_for_project(self, project_id: str) -> List[ProjectMemoryRecord]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM project_memory WHERE project_id = ? ORDER BY created_at ASC", (project_id,)).fetchall()
            return [
                ProjectMemoryRecord(
                    record_id=r["record_id"],
                    project_id=r["project_id"],
                    task_id=r["task_id"],
                    run_id=r["run_id"],
                    domain=PatternDomain(r["domain"]),
                    architecture_facts=json.loads(r["architecture_facts"]),
                    local_findings=json.loads(r["local_findings"]),
                    rejected_hypotheses=json.loads(r["rejected_hypotheses"]),
                    successful_strategies=json.loads(r["successful_strategies"]),
                    failed_strategies=json.loads(r["failed_strategies"]),
                    evidence_refs=json.loads(r["evidence_refs"]),
                    privacy_class=MemoryPrivacyClass(r["privacy_class"]),
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
                for r in rows
            ]


class GlobalPatternRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, pat: PatternRecord) -> PatternRecord:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO global_patterns (
                    pattern_id, domain, title, structural_signature, semantic_signature,
                    indicators, affected_constructs, supporting_evidence_types,
                    successful_analysis_steps, rejected_analysis_steps, validation_method,
                    provenance, confidence_state, privacy_class, observation_count,
                    version, schema_version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pat.pattern_id,
                pat.domain.value,
                pat.title,
                pat.structural_signature,
                pat.semantic_signature,
                json.dumps(pat.indicators),
                json.dumps(pat.affected_constructs),
                json.dumps(pat.supporting_evidence_types),
                json.dumps(pat.successful_analysis_steps),
                json.dumps(pat.rejected_analysis_steps),
                pat.validation_method,
                json.dumps(pat.provenance),
                pat.confidence_state.value,
                pat.privacy_class.value,
                pat.observation_count,
                pat.version,
                pat.schema_version,
                pat.created_at.isoformat(),
                pat.updated_at.isoformat(),
            ))
            conn.commit()
        return pat

    def get(self, pattern_id: str) -> Optional[PatternRecord]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM global_patterns WHERE pattern_id = ?", (pattern_id,)).fetchone()
            if not row:
                return None
            return PatternRecord(
                pattern_id=row["pattern_id"],
                domain=PatternDomain(row["domain"]),
                title=row["title"],
                structural_signature=row["structural_signature"],
                semantic_signature=row["semantic_signature"],
                indicators=json.loads(row["indicators"]),
                affected_constructs=json.loads(row["affected_constructs"]),
                supporting_evidence_types=json.loads(row["supporting_evidence_types"]),
                successful_analysis_steps=json.loads(row["successful_analysis_steps"]),
                rejected_analysis_steps=json.loads(row["rejected_analysis_steps"]),
                validation_method=row["validation_method"],
                provenance=json.loads(row["provenance"]),
                confidence_state=MemoryConfidence(row["confidence_state"]),
                privacy_class=MemoryPrivacyClass(row["privacy_class"]),
                observation_count=row["observation_count"],
                version=row["version"],
                schema_version=row["schema_version"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )

    def list_all(self) -> List[PatternRecord]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM global_patterns ORDER BY created_at ASC").fetchall()
            return [
                PatternRecord(
                    pattern_id=r["pattern_id"],
                    domain=PatternDomain(r["domain"]),
                    title=r["title"],
                    structural_signature=r["structural_signature"],
                    semantic_signature=r["semantic_signature"],
                    indicators=json.loads(r["indicators"]),
                    affected_constructs=json.loads(r["affected_constructs"]),
                    supporting_evidence_types=json.loads(r["supporting_evidence_types"]),
                    successful_analysis_steps=json.loads(r["successful_analysis_steps"]),
                    rejected_analysis_steps=json.loads(r["rejected_analysis_steps"]),
                    validation_method=r["validation_method"],
                    provenance=json.loads(r["provenance"]),
                    confidence_state=MemoryConfidence(r["confidence_state"]),
                    privacy_class=MemoryPrivacyClass(r["privacy_class"]),
                    observation_count=r["observation_count"],
                    version=r["version"],
                    schema_version=r["schema_version"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                )
                for r in rows
            ]


class ResearchStrategyRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, strat: ResearchStrategyRecord) -> ResearchStrategyRecord:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO research_strategies (
                    strategy_id, domain, name, steps, outcome,
                    relevant_conditions, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                strat.strategy_id,
                strat.domain.value,
                strat.name,
                json.dumps(strat.steps),
                strat.outcome.value,
                json.dumps(strat.relevant_conditions),
                strat.notes,
                strat.created_at.isoformat(),
            ))
            conn.commit()
        return strat


class ResearchOutcomeRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, outcome: ResearchOutcomeRecord) -> ResearchOutcomeRecord:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO research_outcomes (
                    outcome_id, project_id, task_id, run_id, domain,
                    analysis_unit_id, hypothesis, confidence,
                    successful_steps, rejected_steps, evidence_refs,
                    is_generalizable, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                outcome.outcome_id,
                outcome.project_id,
                outcome.task_id,
                outcome.run_id,
                outcome.domain.value,
                outcome.analysis_unit_id,
                outcome.hypothesis,
                outcome.confidence.value,
                json.dumps(outcome.successful_steps),
                json.dumps(outcome.rejected_steps),
                json.dumps(outcome.evidence_refs),
                1 if outcome.is_generalizable else 0,
                outcome.created_at.isoformat(),
            ))
            conn.commit()
        return outcome


class MemoryPromotionRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, prom: MemoryPromotionRecord) -> MemoryPromotionRecord:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memory_promotions (
                    promotion_id, project_id, outcome_id, pattern_id,
                    accepted, rejection_reason, sanitized_fields, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prom.promotion_id,
                prom.project_id,
                prom.outcome_id,
                prom.pattern_id,
                1 if prom.accepted else 0,
                prom.rejection_reason,
                json.dumps(prom.sanitized_fields),
                prom.created_at.isoformat(),
            ))
            conn.commit()
        return prom


# Phase 7 Repositories: Repository Intelligence
class ExtendedRepositorySnapshotRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, snap: ExtendedRepositorySnapshot) -> ExtendedRepositorySnapshot:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO repository_snapshots (
                    snapshot_id, repository_id, absolute_root, repository_type, git_commit,
                    archive_hash, file_count, language_summary, build_systems, metadata_systems,
                    symlink_summary, classification_summary, created_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snap.snapshot_id,
                snap.repository_id,
                snap.absolute_root,
                snap.repository_type,
                snap.git_commit,
                snap.archive_hash,
                snap.file_count,
                json.dumps(snap.language_summary),
                json.dumps(snap.build_systems),
                json.dumps(snap.metadata_systems),
                json.dumps(snap.symlink_summary),
                json.dumps(snap.classification_summary),
                snap.created_at.isoformat(),
                snap.schema_version,
            ))
            conn.commit()
        return snap

    def get(self, snapshot_id: str) -> Optional[ExtendedRepositorySnapshot]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM repository_snapshots WHERE snapshot_id = ?", (snapshot_id,)).fetchone()
            if not row:
                return None
            meta_sys = []
            if "metadata_systems" in row.keys() and row["metadata_systems"]:
                try:
                    meta_sys = json.loads(row["metadata_systems"])
                except Exception:
                    meta_sys = []
            return ExtendedRepositorySnapshot(
                snapshot_id=row["snapshot_id"],
                repository_id=row["repository_id"],
                absolute_root=row["absolute_root"],
                repository_type=row["repository_type"],
                git_commit=row["git_commit"],
                archive_hash=row["archive_hash"],
                file_count=row["file_count"],
                language_summary=json.loads(row["language_summary"]),
                build_systems=json.loads(row["build_systems"]),
                metadata_systems=meta_sys,
                symlink_summary=json.loads(row["symlink_summary"]),
                classification_summary=json.loads(row["classification_summary"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                schema_version=row["schema_version"],
            )


class SourceFileRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save_batch(self, files: List[FileClassificationRecord], snapshot_id: str):
        with self.db.get_connection() as conn:
            for f in files:
                conn.execute("""
                    INSERT OR REPLACE INTO source_files (
                        file_id, snapshot_id, rel_path, abs_path, content_hash,
                        classification, language, size_bytes, is_symlink, is_secret,
                        target_ref, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f.file_id,
                    snapshot_id,
                    f.rel_path,
                    f.abs_path,
                    f.content_hash,
                    f.classification.value,
                    f.language,
                    f.size_bytes,
                    1 if f.is_symlink else 0,
                    1 if f.is_secret else 0,
                    f.target_ref,
                    f.created_at.isoformat(),
                ))
            conn.commit()

    def list_for_snapshot(self, snapshot_id: str) -> List[FileClassificationRecord]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM source_files WHERE snapshot_id = ?", (snapshot_id,)).fetchall()
            return [
                FileClassificationRecord(
                    file_id=r["file_id"],
                    rel_path=r["rel_path"],
                    abs_path=r["abs_path"],
                    content_hash=r["content_hash"],
                    classification=FileClassificationType(r["classification"]),
                    language=r["language"],
                    size_bytes=r["size_bytes"],
                    is_symlink=bool(r["is_symlink"]),
                    is_secret=bool(r["is_secret"]),
                    target_ref=r["target_ref"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
                for r in rows
            ]


class AnalysisUnitRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, unit: AnalysisUnit) -> AnalysisUnit:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO analysis_units (
                    analysis_unit_id, repository_id, snapshot_id, unit_type, domain,
                    name, description, anchors, source_files, symbols, build_targets,
                    modules, dependencies, entry_points, assets, trust_boundaries,
                    security_properties, countermeasures, reachable_components,
                    relevance_score, priority, classification, provenance,
                    included_context, excluded_context, expansion_reason,
                    created_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                unit.analysis_unit_id,
                unit.repository_id,
                unit.snapshot_id,
                unit.unit_type.value,
                unit.domain,
                unit.name,
                unit.description,
                json.dumps(unit.anchors),
                json.dumps(unit.source_files),
                json.dumps(unit.symbols),
                json.dumps(unit.build_targets),
                json.dumps(unit.modules),
                json.dumps(unit.dependencies),
                json.dumps(unit.entry_points),
                json.dumps(unit.assets),
                json.dumps(unit.trust_boundaries),
                json.dumps(unit.security_properties),
                json.dumps(unit.countermeasures),
                json.dumps(unit.reachable_components),
                unit.relevance_score,
                unit.priority.value,
                unit.classification,
                json.dumps(unit.provenance),
                json.dumps(unit.included_context),
                json.dumps(unit.excluded_context),
                unit.expansion_reason,
                unit.created_at.isoformat(),
                unit.schema_version,
            ))
            conn.commit()
        return unit

    def get(self, unit_id: str) -> Optional[AnalysisUnit]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM analysis_units WHERE analysis_unit_id = ?", (unit_id,)).fetchone()
            if not row:
                return None
            return AnalysisUnit(
                analysis_unit_id=row["analysis_unit_id"],
                repository_id=row["repository_id"],
                snapshot_id=row["snapshot_id"],
                unit_type=AnalysisUnitType(row["unit_type"]),
                domain=row["domain"],
                name=row["name"],
                description=row["description"],
                anchors=json.loads(row["anchors"]),
                source_files=json.loads(row["source_files"]),
                symbols=json.loads(row["symbols"]),
                build_targets=json.loads(row["build_targets"]),
                modules=json.loads(row["modules"]),
                dependencies=json.loads(row["dependencies"]),
                entry_points=json.loads(row["entry_points"]),
                assets=json.loads(row["assets"]),
                trust_boundaries=json.loads(row["trust_boundaries"]),
                security_properties=json.loads(row["security_properties"]),
                countermeasures=json.loads(row["countermeasures"]),
                reachable_components=json.loads(row["reachable_components"]),
                relevance_score=row["relevance_score"],
                priority=PriorityLevel(row["priority"]),
                classification=row["classification"],
                provenance=json.loads(row["provenance"]),
                included_context=json.loads(row["included_context"]),
                excluded_context=json.loads(row["excluded_context"]),
                expansion_reason=row["expansion_reason"],
                created_at=datetime.fromisoformat(row["created_at"]),
                schema_version=row["schema_version"],
            )

    def list_for_snapshot(self, snapshot_id: str) -> List[AnalysisUnit]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM analysis_units WHERE snapshot_id = ? ORDER BY relevance_score DESC", (snapshot_id,)).fetchall()
            return [
                AnalysisUnit(
                    analysis_unit_id=r["analysis_unit_id"],
                    repository_id=r["repository_id"],
                    snapshot_id=r["snapshot_id"],
                    unit_type=AnalysisUnitType(r["unit_type"]),
                    domain=r["domain"],
                    name=r["name"],
                    description=r["description"],
                    anchors=json.loads(r["anchors"]),
                    source_files=json.loads(r["source_files"]),
                    symbols=json.loads(r["symbols"]),
                    build_targets=json.loads(r["build_targets"]),
                    modules=json.loads(r["modules"]),
                    dependencies=json.loads(r["dependencies"]),
                    entry_points=json.loads(r["entry_points"]),
                    assets=json.loads(r["assets"]),
                    trust_boundaries=json.loads(r["trust_boundaries"]),
                    security_properties=json.loads(r["security_properties"]),
                    countermeasures=json.loads(r["countermeasures"]),
                    reachable_components=json.loads(r["reachable_components"]),
                    relevance_score=r["relevance_score"],
                    priority=PriorityLevel(r["priority"]),
                    classification=r["classification"],
                    provenance=json.loads(r["provenance"]),
                    included_context=json.loads(r["included_context"]),
                    excluded_context=json.loads(r["excluded_context"]),
                    expansion_reason=r["expansion_reason"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                    schema_version=r["schema_version"],
                )
                for r in rows
            ]


class SecuritySurfaceRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, surf: SecuritySurface) -> SecuritySurface:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO security_surfaces (
                    security_surface_id, analysis_unit_id, repository_id, snapshot_id,
                    assets, boundaries, attacker_capabilities, privilege_tiers, entry_points,
                    states, properties, countermeasures, assumptions, provenance, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                surf.security_surface_id,
                surf.analysis_unit_id,
                surf.repository_id,
                surf.snapshot_id,
                json.dumps([a.model_dump() for a in surf.assets]),
                json.dumps([b.model_dump() for b in surf.boundaries]),
                json.dumps([c.value for c in surf.attacker_capabilities]),
                json.dumps(surf.privilege_tiers),
                json.dumps([e.model_dump() for e in surf.entry_points]),
                json.dumps(surf.states),
                json.dumps(surf.properties),
                json.dumps([cm.model_dump() for cm in surf.countermeasures]),
                json.dumps(surf.assumptions),
                json.dumps(surf.provenance),
                surf.schema_version,
            ))
            conn.commit()
        return surf


class SecretQuarantineRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, sec: SecretQuarantineRecord, snapshot_id: str = "") -> SecretQuarantineRecord:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO secrets_quarantine (
                    quarantine_id, snapshot_id, file_path, secret_type,
                    redacted_preview, quarantined_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sec.quarantine_id,
                snapshot_id,
                sec.file_path,
                sec.secret_type,
                sec.redacted_preview,
                sec.quarantined_at.isoformat(),
            ))
            conn.commit()
        return sec

    def list_for_snapshot(self, snapshot_id: str) -> List[SecretQuarantineRecord]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM secrets_quarantine WHERE snapshot_id = ?", (snapshot_id,)).fetchall()
            return [
                SecretQuarantineRecord(
                    quarantine_id=r["quarantine_id"],
                    file_path=r["file_path"],
                    secret_type=r["secret_type"],
                    redacted_preview=r["redacted_preview"],
                    quarantined_at=datetime.fromisoformat(r["quarantined_at"]),
                )
                for r in rows
            ]


from .phase8_repositories import (
    CandidateRepository,
    ReproSpecRepository,
    ReproducerRepository,
    ValidationResultRepository,
)
from .phase9_repositories import (
    TokenUsageRepository,
    TokenBudgetRepository,
    RepositoryEstimateRepository,
    AgentSwitchRepository,
    ModelSwitchRepository,
    ConfigurationRepository,
    TargetRepositoryRepository,
)

