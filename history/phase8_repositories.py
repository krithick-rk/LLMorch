"""
LLMorch Persistence - Phase 8 Repositories
Repository abstractions for CRUD operations across Candidate, ReproSpec,
Reproducer, and ValidationResult.
"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from .database import DatabaseService
from schemas.candidate import Candidate, CandidatePriority
from schemas.reprospec import ReproSpec
from schemas.reproducer import Reproducer, ReproducerState, ReproducerType, ReproducerManifest, Harness, ReproducerInput
from schemas.validation import ValidationResult, ValidationVerdict, DeterminismResult, ReplayComparison, MinimizationResult


class CandidateRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, candidate: Candidate) -> Candidate:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO candidates (
                    candidate_id, task_id, run_id, analysis_unit_id, hypothesis_id,
                    domain, security_property, attack_surface, attack_path,
                    expected_behavior, suspected_behavior, required_evidence, priority,
                    source_references, tool_observations, memory_references, historical_references,
                    created_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    expected_behavior=excluded.expected_behavior,
                    suspected_behavior=excluded.suspected_behavior,
                    priority=excluded.priority,
                    tool_observations=excluded.tool_observations
            """, (
                candidate.candidate_id,
                candidate.task_id,
                candidate.run_id,
                candidate.analysis_unit_id,
                candidate.hypothesis_id,
                candidate.domain,
                candidate.security_property,
                candidate.attack_surface,
                candidate.attack_path,
                candidate.expected_behavior,
                candidate.suspected_behavior,
                json.dumps(candidate.required_evidence),
                candidate.priority.value,
                json.dumps(candidate.source_references),
                json.dumps(candidate.tool_observations),
                json.dumps(candidate.memory_references),
                json.dumps(candidate.historical_references),
                candidate.created_at.isoformat(),
                candidate.schema_version
            ))
            conn.commit()
        return candidate

    def get_by_id(self, candidate_id: str) -> Optional[Candidate]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM candidates WHERE candidate_id = ?", (candidate_id,)).fetchone()
            if not row:
                return None
            return Candidate(
                candidate_id=row["candidate_id"],
                task_id=row["task_id"],
                run_id=row["run_id"],
                analysis_unit_id=row["analysis_unit_id"],
                hypothesis_id=row["hypothesis_id"],
                domain=row["domain"],
                security_property=row["security_property"],
                attack_surface=row["attack_surface"],
                attack_path=row["attack_path"],
                expected_behavior=row["expected_behavior"],
                suspected_behavior=row["suspected_behavior"],
                required_evidence=json.loads(row["required_evidence"]),
                priority=CandidatePriority(row["priority"]),
                source_references=json.loads(row["source_references"]),
                tool_observations=json.loads(row["tool_observations"]),
                memory_references=json.loads(row["memory_references"]),
                historical_references=json.loads(row["historical_references"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                schema_version=row["schema_version"]
            )


class ReproSpecRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, spec: ReproSpec) -> ReproSpec:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO repro_specs (
                    spec_id, candidate_id, objective, domain, reproducer_type,
                    preconditions, entry_point, trigger, expected_failure,
                    required_harness, required_tools, build_procedure, run_procedure,
                    validation_signal, requested_replay_count, environment_requirements,
                    created_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(spec_id) DO UPDATE SET
                    expected_failure=excluded.expected_failure,
                    run_procedure=excluded.run_procedure
            """, (
                spec.spec_id,
                spec.candidate_id,
                spec.objective,
                spec.domain,
                spec.reproducer_type.value,
                json.dumps(spec.preconditions),
                spec.entry_point,
                spec.trigger,
                json.dumps(spec.expected_failure),
                json.dumps(spec.required_harness),
                json.dumps(spec.required_tools),
                spec.build_procedure,
                spec.run_procedure,
                spec.validation_signal,
                spec.requested_replay_count,
                json.dumps(spec.environment_requirements),
                spec.created_at.isoformat(),
                spec.schema_version
            ))
            conn.commit()
        return spec

    def get_by_id(self, spec_id: str) -> Optional[ReproSpec]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM repro_specs WHERE spec_id = ?", (spec_id,)).fetchone()
            if not row:
                return None
            return ReproSpec(
                spec_id=row["spec_id"],
                candidate_id=row["candidate_id"],
                objective=row["objective"],
                domain=row["domain"],
                reproducer_type=ReproducerType(row["reproducer_type"]),
                preconditions=json.loads(row["preconditions"]),
                entry_point=row["entry_point"],
                trigger=row["trigger"],
                expected_failure=json.loads(row["expected_failure"]),
                required_harness=json.loads(row["required_harness"]),
                required_tools=json.loads(row["required_tools"]),
                build_procedure=row["build_procedure"],
                run_procedure=row["run_procedure"],
                validation_signal=row["validation_signal"],
                requested_replay_count=row["requested_replay_count"],
                environment_requirements=json.loads(row["environment_requirements"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                schema_version=row["schema_version"]
            )


class ReproducerRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, repro: Reproducer) -> Reproducer:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO reproducers (
                    reproducer_id, candidate_id, spec_id, reproducer_type,
                    state, manifest, harness, inputs, quarantined_files,
                    created_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(reproducer_id) DO UPDATE SET
                    state=excluded.state,
                    manifest=excluded.manifest
            """, (
                repro.reproducer_id,
                repro.candidate_id,
                repro.spec_id,
                repro.reproducer_type.value,
                repro.state.value,
                repro.manifest.model_dump_json(),
                repro.harness.model_dump_json() if repro.harness else "{}",
                json.dumps([inp.model_dump() for inp in repro.inputs]),
                json.dumps(repro.quarantined_files),
                repro.created_at.isoformat(),
                repro.schema_version
            ))
            conn.commit()
        return repro

    def get_by_id(self, reproducer_id: str) -> Optional[Reproducer]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM reproducers WHERE reproducer_id = ?", (reproducer_id,)).fetchone()
            if not row:
                return None
            manifest_dict = json.loads(row["manifest"])
            harness_dict = json.loads(row["harness"])
            inputs_list = json.loads(row["inputs"])
            return Reproducer(
                reproducer_id=row["reproducer_id"],
                candidate_id=row["candidate_id"],
                spec_id=row["spec_id"],
                reproducer_type=ReproducerType(row["reproducer_type"]),
                state=ReproducerState(row["state"]),
                manifest=ReproducerManifest(**manifest_dict),
                harness=Harness(**harness_dict) if harness_dict else None,
                inputs=[ReproducerInput(**i) for i in inputs_list],
                quarantined_files=json.loads(row["quarantined_files"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                schema_version=row["schema_version"]
            )

    def list_all(self) -> List[Reproducer]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM reproducers ORDER BY created_at DESC").fetchall()
            results = []
            for row in rows:
                manifest_dict = json.loads(row["manifest"])
                harness_dict = json.loads(row["harness"])
                inputs_list = json.loads(row["inputs"])
                results.append(Reproducer(
                    reproducer_id=row["reproducer_id"],
                    candidate_id=row["candidate_id"],
                    spec_id=row["spec_id"],
                    reproducer_type=ReproducerType(row["reproducer_type"]),
                    state=ReproducerState(row["state"]),
                    manifest=ReproducerManifest(**manifest_dict),
                    harness=Harness(**harness_dict) if harness_dict else None,
                    inputs=[ReproducerInput(**i) for i in inputs_list],
                    quarantined_files=json.loads(row["quarantined_files"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    schema_version=row["schema_version"]
                ))
            return results


class ValidationResultRepository:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def save(self, res: ValidationResult) -> ValidationResult:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO validation_results (
                    validation_id, candidate_id, reproducer_id, verdict,
                    confidence_score, determinism, replay_comparison, minimization,
                    supporting_evidence_ids, execution_trace_ids, reasoning, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(validation_id) DO UPDATE SET
                    verdict=excluded.verdict,
                    confidence_score=excluded.confidence_score,
                    reasoning=excluded.reasoning
            """, (
                res.validation_id,
                res.candidate_id,
                res.reproducer_id,
                res.verdict.value,
                res.confidence_score,
                res.determinism.model_dump_json(),
                res.replay_comparison.model_dump_json(),
                res.minimization.model_dump_json() if res.minimization else None,
                json.dumps(res.supporting_evidence_ids),
                json.dumps(res.execution_trace_ids),
                res.reasoning,
                res.created_at.isoformat()
            ))
            conn.commit()
        return res

    def get_by_id(self, validation_id: str) -> Optional[ValidationResult]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM validation_results WHERE validation_id = ?", (validation_id,)).fetchone()
            if not row:
                return None
            det_dict = json.loads(row["determinism"])
            rep_dict = json.loads(row["replay_comparison"])
            min_dict = json.loads(row["minimization"]) if row["minimization"] else None
            return ValidationResult(
                validation_id=row["validation_id"],
                candidate_id=row["candidate_id"],
                reproducer_id=row["reproducer_id"],
                verdict=ValidationVerdict(row["verdict"]),
                confidence_score=row["confidence_score"],
                determinism=DeterminismResult(**det_dict),
                replay_comparison=ReplayComparison(**rep_dict),
                minimization=MinimizationResult(**min_dict) if min_dict else None,
                supporting_evidence_ids=json.loads(row["supporting_evidence_ids"]),
                execution_trace_ids=json.loads(row["execution_trace_ids"]),
                reasoning=row["reasoning"],
                created_at=datetime.fromisoformat(row["created_at"])
            )
