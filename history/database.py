"""
LLMorch Persistence - SQLite Database Service (Phase 7 Repository Intelligence)
Manages connection lifecycle, table migrations, and foreign key integrity.
"""

import sqlite3
import os
import logging
import threading
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ConnectionContext:
    """Thread-safe context manager and proxy for SQLite connections."""

    def __init__(self, conn: sqlite3.Connection, lock: threading.RLock):
        self._conn = conn
        self._lock = lock

    def __enter__(self):
        self._lock.acquire()
        self._conn.__enter__()
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return self._conn.__exit__(exc_type, exc_val, exc_tb)
        finally:
            self._lock.release()

    def execute(self, *args, **kwargs):
        with self._lock:
            return self._conn.execute(*args, **kwargs)

    def cursor(self, *args, **kwargs):
        with self._lock:
            return self._conn.cursor(*args, **kwargs)

    def commit(self, *args, **kwargs):
        with self._lock:
            return self._conn.commit(*args, **kwargs)

    def rollback(self, *args, **kwargs):
        with self._lock:
            return self._conn.rollback(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._conn, name)


class DatabaseService:
    """
    Manages SQLite connection pooling and schema migrations.
    Supports in-memory mode for testing and file-backed mode for persistence.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._lock = threading.RLock()
        if db_path is None or db_path == ":memory:":
            self.db_path = ":memory:"
            self._is_memory = True
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON;")
        else:
            self._is_memory = False
            self.db_path = str(Path(db_path).resolve())
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._conn = None

        self._init_db()

    def get_connection(self):
        if self._is_memory:
            return ConnectionContext(self._conn, self._lock)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        """Initializes tables for Phase 0–7 data contracts."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Tasks table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                workflow_id TEXT,
                parent_task_id TEXT,
                objective TEXT NOT NULL,
                inputs TEXT NOT NULL,
                dependencies TEXT NOT NULL,
                required_capabilities TEXT NOT NULL,
                preferred_roles TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                workspace_policy TEXT NOT NULL,
                tool_policy TEXT NOT NULL,
                budget TEXT NOT NULL,
                status TEXT NOT NULL,
                assigned_agent_id TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                acceptance_criteria TEXT NOT NULL,
                result_ref TEXT,
                schema_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                FOREIGN KEY (parent_task_id) REFERENCES tasks(task_id) ON DELETE SET NULL
            );
            """)

            # Agents table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                interface TEXT NOT NULL,
                model TEXT NOT NULL,
                capabilities TEXT NOT NULL,
                protocols TEXT NOT NULL,
                permissions TEXT NOT NULL,
                health TEXT NOT NULL,
                availability INTEGER NOT NULL,
                concurrency_limit INTEGER NOT NULL,
                usage_status TEXT NOT NULL,
                quota_status TEXT NOT NULL,
                workspace_class TEXT NOT NULL,
                auth_profile TEXT NOT NULL,
                adapter_version TEXT NOT NULL,
                metadata TEXT NOT NULL,
                schema_version TEXT NOT NULL
            );
            """)

            # Runs table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                parent_run_id TEXT,
                agent_id TEXT NOT NULL,
                adapter_version TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                process_id INTEGER,
                exit_status INTEGER,
                workspace_id TEXT NOT NULL,
                environment_fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,
                failure_code TEXT,
                failure_reason TEXT,
                schema_version TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
            );
            """)

            # Checkpoints table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                workflow_id TEXT,
                run_id TEXT,
                completed_subtasks TEXT NOT NULL,
                remaining_subtasks TEXT NOT NULL,
                task_state TEXT NOT NULL,
                artifact_refs TEXT NOT NULL,
                evidence_refs TEXT NOT NULL,
                finding_refs TEXT NOT NULL,
                hypothesis_refs TEXT NOT NULL,
                workspace_snapshot TEXT NOT NULL,
                repository_snapshot TEXT NOT NULL,
                next_action TEXT,
                recovery_context TEXT,
                is_valid INTEGER NOT NULL DEFAULT 1,
                invalidation_reason TEXT,
                schema_version TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # Artifacts table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                uri TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                retention_class TEXT NOT NULL,
                access_policy TEXT NOT NULL,
                schema_version TEXT NOT NULL
            );
            """)

            # Evidence table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                raw_hash TEXT NOT NULL,
                canonical_hash TEXT NOT NULL,
                semantic_fingerprint TEXT NOT NULL,
                environment_fingerprint TEXT NOT NULL,
                exit_status INTEGER,
                provenance TEXT NOT NULL,
                schema_version TEXT NOT NULL
            );
            """)

            # Findings table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                finding_id TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL UNIQUE,
                hypothesis TEXT NOT NULL,
                locations TEXT NOT NULL,
                supporting_evidence TEXT NOT NULL,
                contradicting_evidence TEXT NOT NULL,
                validation_method TEXT,
                validator_result TEXT,
                state TEXT NOT NULL,
                lineage TEXT NOT NULL,
                timestamps TEXT NOT NULL,
                schema_version TEXT NOT NULL
            );
            """)

            # Events table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                run_id TEXT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                tool TEXT,
                payload_ref TEXT,
                payload TEXT NOT NULL,
                parent_event_id TEXT,
                schema_version TEXT NOT NULL
            );
            """)

            # Phase 6 Tables: Project Memory
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_memory (
                record_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                task_id TEXT,
                run_id TEXT,
                domain TEXT NOT NULL,
                architecture_facts TEXT NOT NULL,
                local_findings TEXT NOT NULL,
                rejected_hypotheses TEXT NOT NULL,
                successful_strategies TEXT NOT NULL,
                failed_strategies TEXT NOT NULL,
                evidence_refs TEXT NOT NULL,
                privacy_class TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # Phase 6 Tables: Global Pattern Memory
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS global_patterns (
                pattern_id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                title TEXT NOT NULL,
                structural_signature TEXT NOT NULL,
                semantic_signature TEXT NOT NULL,
                indicators TEXT NOT NULL,
                affected_constructs TEXT NOT NULL,
                supporting_evidence_types TEXT NOT NULL,
                successful_analysis_steps TEXT NOT NULL,
                rejected_analysis_steps TEXT NOT NULL,
                validation_method TEXT,
                provenance TEXT NOT NULL,
                confidence_state TEXT NOT NULL,
                privacy_class TEXT NOT NULL,
                observation_count INTEGER NOT NULL DEFAULT 1,
                version INTEGER NOT NULL DEFAULT 1,
                schema_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # Phase 6 Tables: Research Strategies
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS research_strategies (
                strategy_id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                name TEXT NOT NULL,
                steps TEXT NOT NULL,
                outcome TEXT NOT NULL,
                relevant_conditions TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # Phase 6 Tables: Research Outcomes
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS research_outcomes (
                outcome_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                analysis_unit_id TEXT,
                hypothesis TEXT NOT NULL,
                confidence TEXT NOT NULL,
                successful_steps TEXT NOT NULL,
                rejected_steps TEXT NOT NULL,
                evidence_refs TEXT NOT NULL,
                is_generalizable INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """)

            # Phase 6 Tables: Memory Promotions
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_promotions (
                promotion_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                outcome_id TEXT NOT NULL,
                pattern_id TEXT,
                accepted INTEGER NOT NULL,
                rejection_reason TEXT,
                sanitized_fields TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # Phase 7 Tables: Repository Snapshots
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS repository_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                repository_id TEXT NOT NULL,
                absolute_root TEXT NOT NULL,
                repository_type TEXT NOT NULL,
                git_commit TEXT,
                archive_hash TEXT NOT NULL,
                file_count INTEGER NOT NULL,
                language_summary TEXT NOT NULL,
                build_systems TEXT NOT NULL,
                metadata_systems TEXT DEFAULT '[]',
                symlink_summary TEXT NOT NULL,
                classification_summary TEXT NOT NULL,
                created_at TEXT NOT NULL,
                schema_version TEXT NOT NULL
            );
            """)
            try:
                cursor.execute("ALTER TABLE repository_snapshots ADD COLUMN metadata_systems TEXT DEFAULT '[]'")
            except Exception:
                pass

            # Phase 7 Tables: Source Files
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_files (
                file_id TEXT PRIMARY KEY,
                snapshot_id TEXT NOT NULL,
                rel_path TEXT NOT NULL,
                abs_path TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                classification TEXT NOT NULL,
                language TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                is_symlink INTEGER NOT NULL DEFAULT 0,
                is_secret INTEGER NOT NULL DEFAULT 0,
                target_ref TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # Phase 7 Tables: Build Targets
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS build_targets (
                target_id TEXT PRIMARY KEY,
                snapshot_id TEXT NOT NULL,
                build_system TEXT NOT NULL,
                target_name TEXT NOT NULL,
                defined_in_file TEXT NOT NULL,
                source_files TEXT NOT NULL,
                dependencies TEXT NOT NULL,
                output_artifacts TEXT NOT NULL
            );
            """)

            # Phase 7 Tables: Symbols
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS symbols (
                symbol_id TEXT PRIMARY KEY,
                snapshot_id TEXT NOT NULL,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                language TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line_start INTEGER NOT NULL,
                line_end INTEGER NOT NULL,
                parent_symbol_id TEXT,
                metadata TEXT NOT NULL
            );
            """)

            # Phase 7 Tables: Dependencies
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS dependencies (
                relation_id TEXT PRIMARY KEY,
                snapshot_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                provenance TEXT NOT NULL
            );
            """)

            # Phase 7 Tables: HW-SW Contracts
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS hw_sw_contracts (
                contract_id TEXT PRIMARY KEY,
                snapshot_id TEXT NOT NULL,
                register_name TEXT NOT NULL,
                rtl_module TEXT,
                hjson_ref TEXT,
                header_ref TEXT,
                dif_ref TEXT,
                access_policy TEXT,
                lock_bits TEXT NOT NULL
            );
            """)

            # Phase 7 Tables: Analysis Units
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_units (
                analysis_unit_id TEXT PRIMARY KEY,
                repository_id TEXT NOT NULL,
                snapshot_id TEXT NOT NULL,
                unit_type TEXT NOT NULL,
                domain TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                anchors TEXT NOT NULL,
                source_files TEXT NOT NULL,
                symbols TEXT NOT NULL,
                build_targets TEXT NOT NULL,
                modules TEXT NOT NULL,
                dependencies TEXT NOT NULL,
                entry_points TEXT NOT NULL,
                assets TEXT NOT NULL,
                trust_boundaries TEXT NOT NULL,
                security_properties TEXT NOT NULL,
                countermeasures TEXT NOT NULL,
                reachable_components TEXT NOT NULL,
                relevance_score REAL NOT NULL,
                priority TEXT NOT NULL,
                classification TEXT NOT NULL,
                provenance TEXT NOT NULL,
                included_context TEXT NOT NULL,
                excluded_context TEXT NOT NULL,
                expansion_reason TEXT,
                created_at TEXT NOT NULL,
                schema_version TEXT NOT NULL
            );
            """)

            # Phase 7 Tables: Security Surfaces
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_surfaces (
                security_surface_id TEXT PRIMARY KEY,
                analysis_unit_id TEXT,
                repository_id TEXT NOT NULL,
                snapshot_id TEXT NOT NULL,
                assets TEXT NOT NULL,
                boundaries TEXT NOT NULL,
                attacker_capabilities TEXT NOT NULL,
                privilege_tiers TEXT NOT NULL,
                entry_points TEXT NOT NULL,
                states TEXT NOT NULL,
                properties TEXT NOT NULL,
                countermeasures TEXT NOT NULL,
                assumptions TEXT NOT NULL,
                provenance TEXT NOT NULL,
                schema_version TEXT NOT NULL
            );
            """)

            # Phase 7 Tables: Secrets Quarantine
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS secrets_quarantine (
                quarantine_id TEXT PRIMARY KEY,
                snapshot_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                secret_type TEXT NOT NULL,
                redacted_preview TEXT NOT NULL,
                quarantined_at TEXT NOT NULL
            );
            """)

            # Phase 7 Tables: Context Expansions
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS context_expansions (
                expansion_id TEXT PRIMARY KEY,
                analysis_unit_id TEXT NOT NULL,
                requesting_agent_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                expanded_paths TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # Global Intelligence Plane Tables
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS global_concepts (
                concept_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                description TEXT NOT NULL,
                related_cwe TEXT NOT NULL,
                provenance TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS vulnerability_patterns (
                pattern_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                vulnerability_family TEXT NOT NULL,
                domain TEXT NOT NULL,
                structural_signature TEXT NOT NULL,
                semantic_signature TEXT,
                behavioral_signature TEXT,
                indicators TEXT NOT NULL,
                suggested_investigation_steps TEXT NOT NULL,
                recommended_tool_classes TEXT NOT NULL,
                confidence REAL NOT NULL,
                privacy_class TEXT NOT NULL,
                source_type TEXT NOT NULL,
                observation_count INTEGER NOT NULL,
                provenance TEXT NOT NULL,
                created_at TEXT NOT NULL,
                version TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_invariants (
                invariant_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                domain TEXT NOT NULL,
                formal_expression TEXT,
                natural_language TEXT NOT NULL,
                affected_components TEXT NOT NULL,
                recommended_tools TEXT NOT NULL,
                provenance TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS attack_surface_patterns (
                pattern_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                boundary_type TEXT NOT NULL,
                entry_points TEXT NOT NULL,
                common_attack_paths TEXT NOT NULL,
                required_capabilities TEXT NOT NULL,
                provenance TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS investigation_strategies (
                strategy_id TEXT PRIMARY KEY,
                vulnerability_family TEXT NOT NULL,
                recommended_decomposition TEXT NOT NULL,
                success_rate REAL NOT NULL,
                historical_failures TEXT NOT NULL,
                provenance TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS false_positive_patterns (
                fp_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                vulnerability_family TEXT NOT NULL,
                distinguishing_factors TEXT NOT NULL,
                countermeasures_present TEXT NOT NULL,
                provenance TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS tool_evidence_patterns (
                guidance_id TEXT PRIMARY KEY,
                vulnerability_family TEXT NOT NULL,
                domain TEXT NOT NULL,
                primary_tools TEXT NOT NULL,
                secondary_tools TEXT NOT NULL,
                required_evidence_artifacts TEXT NOT NULL,
                provenance TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_records (
                feedback_id TEXT PRIMARY KEY,
                finding_id TEXT,
                hypothesis_reference TEXT,
                project_id TEXT NOT NULL,
                snapshot_id TEXT,
                analysis_unit_id TEXT,
                reviewer TEXT NOT NULL,
                label TEXT NOT NULL,
                reason TEXT NOT NULL,
                corrected_localization TEXT,
                corrected_security_property TEXT,
                corrected_attack_path TEXT,
                supporting_evidence_refs TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_promotions (
                promotion_id TEXT PRIMARY KEY,
                source_project_id TEXT NOT NULL,
                source_finding_id TEXT,
                proposed_pattern_id TEXT NOT NULL,
                accepted INTEGER NOT NULL,
                rejection_reason TEXT,
                sanitized_fields TEXT NOT NULL,
                egress_policy_applied TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # Phase 8 Tables
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                analysis_unit_id TEXT NOT NULL,
                hypothesis_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                security_property TEXT NOT NULL,
                attack_surface TEXT NOT NULL,
                attack_path TEXT NOT NULL,
                expected_behavior TEXT NOT NULL,
                suspected_behavior TEXT NOT NULL,
                required_evidence TEXT NOT NULL,
                priority TEXT NOT NULL,
                source_references TEXT NOT NULL,
                tool_observations TEXT NOT NULL,
                memory_references TEXT NOT NULL,
                historical_references TEXT NOT NULL,
                created_at TEXT NOT NULL,
                schema_version TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS repro_specs (
                spec_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                objective TEXT NOT NULL,
                domain TEXT NOT NULL,
                reproducer_type TEXT NOT NULL,
                preconditions TEXT NOT NULL,
                entry_point TEXT NOT NULL,
                trigger TEXT NOT NULL,
                expected_failure TEXT NOT NULL,
                required_harness TEXT NOT NULL,
                required_tools TEXT NOT NULL,
                build_procedure TEXT NOT NULL,
                run_procedure TEXT NOT NULL,
                validation_signal TEXT NOT NULL,
                requested_replay_count INTEGER NOT NULL,
                environment_requirements TEXT NOT NULL,
                created_at TEXT NOT NULL,
                schema_version TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS reproducers (
                reproducer_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                spec_id TEXT NOT NULL,
                reproducer_type TEXT NOT NULL,
                state TEXT NOT NULL,
                manifest TEXT NOT NULL,
                harness TEXT NOT NULL,
                inputs TEXT NOT NULL,
                quarantined_files TEXT NOT NULL,
                created_at TEXT NOT NULL,
                schema_version TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sandbox_executions (
                execution_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                reproducer_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                command TEXT NOT NULL,
                exit_code INTEGER NOT NULL,
                stdout_hash TEXT NOT NULL,
                stderr_hash TEXT NOT NULL,
                wall_time_seconds REAL NOT NULL,
                environment_fingerprint TEXT NOT NULL,
                network_policy TEXT NOT NULL,
                trace_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS validation_results (
                validation_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                reproducer_id TEXT NOT NULL,
                verdict TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                determinism TEXT NOT NULL,
                replay_comparison TEXT NOT NULL,
                minimization TEXT,
                supporting_evidence_ids TEXT NOT NULL,
                execution_trace_ids TEXT NOT NULL,
                reasoning TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # Phase 9 — add columns that the API layer needs (safe, idempotent)
            _p9_migrations = [
                # events: add task_id and entity columns for timeline filtering
                "ALTER TABLE events ADD COLUMN task_id TEXT",
                "ALTER TABLE events ADD COLUMN entity_type TEXT",
                "ALTER TABLE events ADD COLUMN entity_id TEXT",
                # evidence: add display columns
                "ALTER TABLE evidence ADD COLUMN finding_id TEXT",
                "ALTER TABLE evidence ADD COLUMN source_tool TEXT",
                "ALTER TABLE evidence ADD COLUMN timestamp TEXT",
                "ALTER TABLE evidence ADD COLUMN tool_version TEXT",
                "ALTER TABLE evidence ADD COLUMN command TEXT",
                "ALTER TABLE evidence ADD COLUMN stdout TEXT",
                "ALTER TABLE evidence ADD COLUMN stderr TEXT",
                "ALTER TABLE evidence ADD COLUMN exit_code INTEGER",
                "ALTER TABLE evidence ADD COLUMN sandbox_id TEXT",
                "ALTER TABLE evidence ADD COLUMN semantic_identity TEXT",
                # findings: add state/severity/timestamps
                "ALTER TABLE findings ADD COLUMN task_id TEXT",
                "ALTER TABLE findings ADD COLUMN state TEXT DEFAULT 'OPEN'",
                "ALTER TABLE findings ADD COLUMN severity TEXT",
                "ALTER TABLE findings ADD COLUMN evidence_ids TEXT",
                "ALTER TABLE findings ADD COLUMN artifact_ids TEXT",
                "ALTER TABLE findings ADD COLUMN affected_locations TEXT",
                "ALTER TABLE findings ADD COLUMN confidence REAL",
                "ALTER TABLE findings ADD COLUMN notes TEXT",
                "ALTER TABLE findings ADD COLUMN created_at TEXT",
                "ALTER TABLE findings ADD COLUMN updated_at TEXT",
                # validation_results: add finding_id/timestamp/validator_name
                "ALTER TABLE validation_results ADD COLUMN finding_id TEXT",
                "ALTER TABLE validation_results ADD COLUMN timestamp TEXT",
                "ALTER TABLE validation_results ADD COLUMN validator_name TEXT",
                "ALTER TABLE validation_results ADD COLUMN replay_count INTEGER DEFAULT 0",
                # reproducers: add finding_id/status/manifest_hash
                "ALTER TABLE reproducers ADD COLUMN finding_id TEXT",
                "ALTER TABLE reproducers ADD COLUMN status TEXT DEFAULT 'UNKNOWN'",
                "ALTER TABLE reproducers ADD COLUMN manifest_hash TEXT",
                # repository_snapshots: add family/branch/tag/total_files
                "ALTER TABLE repository_snapshots ADD COLUMN family TEXT",
                "ALTER TABLE repository_snapshots ADD COLUMN branch TEXT",
                "ALTER TABLE repository_snapshots ADD COLUMN tag TEXT",
                "ALTER TABLE repository_snapshots ADD COLUMN total_files INTEGER DEFAULT 0",
                # analysis_units: add security_critical flag
                "ALTER TABLE analysis_units ADD COLUMN security_critical INTEGER DEFAULT 0",
                # agents: add registered_at
                "ALTER TABLE agents ADD COLUMN registered_at TEXT",
                # runs: add start_time/end_time aliases (schema uses start_time already)
                "ALTER TABLE runs ADD COLUMN start_time_api TEXT",
                # Phase 9.1 additions
                "ALTER TABLE agents ADD COLUMN role TEXT DEFAULT 'general_analysis'",
                "ALTER TABLE agents ADD COLUMN status TEXT DEFAULT 'ACTIVE'",
                "ALTER TABLE agents ADD COLUMN enabled INTEGER DEFAULT 1",
                "ALTER TABLE agents ADD COLUMN supported_models TEXT DEFAULT '[]'",
                "ALTER TABLE agents ADD COLUMN current_model_id TEXT",
                "ALTER TABLE tasks ADD COLUMN model_id TEXT",
                "ALTER TABLE runs ADD COLUMN model_id TEXT",
            ]
            for sql in _p9_migrations:
                try:
                    cursor.execute(sql)
                except Exception:
                    pass  # Column already exists — idempotent

            # Phase 9.1 Tables
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS models (
                model_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                display_name TEXT NOT NULL,
                context_window INTEGER NOT NULL,
                max_output_tokens INTEGER NOT NULL,
                input_token_tracking_supported INTEGER NOT NULL DEFAULT 1,
                output_token_tracking_supported INTEGER NOT NULL DEFAULT 1,
                token_estimation_method TEXT NOT NULL,
                capabilities TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                cost_per_million_input REAL DEFAULT 0.0,
                cost_per_million_output REAL DEFAULT 0.0,
                metadata TEXT NOT NULL,
                created_at TEXT NOT NULL,
                schema_version TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_model_capabilities (
                mapping_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                model_id TEXT NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                priority INTEGER NOT NULL DEFAULT 10,
                notes TEXT,
                created_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                record_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                attempt_id TEXT,
                agent_id TEXT NOT NULL,
                model_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                input_tokens_actual INTEGER NOT NULL DEFAULT 0,
                output_tokens_actual INTEGER NOT NULL DEFAULT 0,
                total_tokens_actual INTEGER NOT NULL DEFAULT 0,
                input_tokens_estimated INTEGER NOT NULL DEFAULT 0,
                output_tokens_estimated INTEGER NOT NULL DEFAULT 0,
                total_tokens_estimated INTEGER NOT NULL DEFAULT 0,
                input_source TEXT NOT NULL,
                output_source TEXT NOT NULL,
                token_source TEXT NOT NULL,
                is_estimated INTEGER NOT NULL DEFAULT 0,
                token_limit INTEGER,
                tokens_remaining INTEGER,
                created_at TEXT NOT NULL,
                schema_version TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_budgets (
                budget_id TEXT PRIMARY KEY,
                run_id TEXT,
                scope_type TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                budget_limit INTEGER NOT NULL,
                consumed INTEGER NOT NULL DEFAULT 0,
                remaining INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'AVAILABLE',
                updated_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS repository_token_estimates (
                estimate_id TEXT PRIMARY KEY,
                repository_path TEXT NOT NULL,
                snapshot_id TEXT,
                total_files INTEGER NOT NULL,
                source_files INTEGER NOT NULL,
                security_relevant_files INTEGER NOT NULL,
                excluded_files INTEGER NOT NULL,
                raw_tokens INTEGER NOT NULL,
                llm_scoped_tokens INTEGER NOT NULL,
                analysis_unit_tokens INTEGER NOT NULL,
                context_expansion_tokens INTEGER NOT NULL,
                initial_analysis_tokens INTEGER NOT NULL,
                followup_tokens INTEGER NOT NULL,
                estimated_total INTEGER NOT NULL,
                recommended_budget INTEGER NOT NULL,
                estimation_method TEXT NOT NULL,
                confidence TEXT NOT NULL,
                breakdown_by_language TEXT NOT NULL,
                breakdown_by_stage TEXT NOT NULL,
                created_at TEXT NOT NULL,
                schema_version TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_switches (
                switch_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                previous_agent_id TEXT NOT NULL,
                new_agent_id TEXT NOT NULL,
                previous_model_id TEXT,
                new_model_id TEXT,
                switch_type TEXT NOT NULL,
                reason TEXT NOT NULL,
                checkpoint_id TEXT,
                resume_action TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'COMPLETED',
                created_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_switches (
                switch_id TEXT PRIMARY KEY,
                task_id TEXT,
                run_id TEXT,
                agent_id TEXT NOT NULL,
                previous_model_id TEXT NOT NULL,
                new_model_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                scope TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuration_records (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL
            );
            """)

            conn.commit()
            logger.info("Database schema initialized successfully (Phase 0-9.1 tables verified).")


def get_db_path() -> str:
    """
    Return the canonical path to the persistent LLMorch database.
    Respects LLMORCH_DB_PATH env override for testing.
    """
    import os
    override = os.environ.get("LLMORCH_DB_PATH")
    if override:
        return override
    here = Path(__file__).resolve().parent
    return str(here / "llmorch.db")
