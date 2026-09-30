"""
IdService — Persistent Hierarchical Project-Local Identifier Engine
Sections 17, 18, 19, 44, 45, 46, 47, 48, 49, 50:
- Allocates persistent sequence numbers per project and entity type.
- Format:
  Project: PROJ-001
  Run: PROJ-001-RUN-001
  Plan: PROJ-001-PLAN-001
  Plan Version: PROJ-001-PLAN-001-V1
  WorkPackage: PROJ-001-WP-001
  Objective: PROJ-001-OBJ-001
  Task: PROJ-001-TASK-001
  Attempt: PROJ-001-ATT-001
  Artifact: PROJ-001-ART-001
  Evidence: PROJ-001-EVI-001
  Finding: PROJ-001-VUL-001
  Question: PROJ-001-Q-001
  Decision: PROJ-001-DEC-001
  Context Pack: PROJ-001-CTX-001
  Tool Run: PROJ-001-TOOL-001
  Handoff: PROJ-001-HO-001
- Compact short ID (e.g., EVI-001, TASK-001) alongside full hierarchical ID.
- Keeps internal UUIDs intact; adds display_id and sequence_no.
"""

from __future__ import annotations
import sqlite3
from typing import Dict, Any, Tuple, Optional


ENTITY_PREFIXES = {
    "PROJECT": "PROJ",
    "RUN": "RUN",
    "PLAN": "PLAN",
    "WP": "WP",
    "OBJ": "OBJ",
    "TASK": "TASK",
    "ATT": "ATT",
    "ART": "ART",
    "EVI": "EVI",
    "VUL": "VUL",
    "Q": "Q",
    "DEC": "DEC",
    "CTX": "CTX",
    "TOOL": "TOOL",
    "HO": "HO",
}


class IdService:
    @staticmethod
    def ensure_sequence_table(conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_id_sequences (
                project_id TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                last_sequence INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (project_id, entity_type)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_agent_preferences (
                project_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                is_allowed INTEGER NOT NULL DEFAULT 1,
                is_preferred INTEGER NOT NULL DEFAULT 0,
                role_preference TEXT,
                execution_preference TEXT,
                PRIMARY KEY (project_id, agent_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_handoffs (
                handoff_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                source_agent_id TEXT NOT NULL,
                destination_agent_id TEXT NOT NULL,
                task_id TEXT,
                run_id TEXT,
                reason TEXT NOT NULL,
                files TEXT DEFAULT '[]',
                context_pack_id TEXT,
                evidence_refs TEXT DEFAULT '[]',
                timestamp TEXT NOT NULL
            )
        """)
        # Ensure display_id and sequence_no columns exist across core tables
        tables_to_augment = [
            "projects", "verification_plans", "work_packages",
            "verification_objectives", "runs", "tasks", "evidence", "findings"
        ]
        for tbl in tables_to_augment:
            try:
                tbl_check = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tbl,)).fetchone()
                if not tbl_check:
                    continue
                cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
                if "display_id" not in cols:
                    conn.execute(f"ALTER TABLE {tbl} ADD COLUMN display_id TEXT")
                if "sequence_no" not in cols:
                    conn.execute(f"ALTER TABLE {tbl} ADD COLUMN sequence_no INTEGER")
                if tbl == "evidence" and "duplicate_of_id" not in cols:
                    conn.execute(f"ALTER TABLE {tbl} ADD COLUMN duplicate_of_id TEXT")
                if tbl == "tasks":
                    for task_col in ["current_stage", "current_file", "current_function", "current_tool", "stop_reason", "last_heartbeat_at"]:
                        if task_col not in cols:
                            try:
                                conn.execute(f"ALTER TABLE tasks ADD COLUMN {task_col} TEXT")
                            except Exception:
                                pass
            except Exception:
                pass

    @classmethod
    def get_project_display_id(cls, conn: sqlite3.Connection, project_id: str) -> str:
        """Retrieves or derives the project's stable display ID (e.g. PROJ-001)."""
        try:
            row = conn.execute(
                "SELECT display_id, sequence_no FROM projects WHERE project_id = ?",
                (project_id,)
            ).fetchone()
            if row and row["display_id"]:
                return row["display_id"]

            # If not yet set, allocate a sequence number for projects under global namespace
            cls.ensure_sequence_table(conn)
            seq_row = conn.execute(
                "SELECT last_sequence FROM project_id_sequences WHERE project_id = '__GLOBAL__' AND entity_type = 'PROJECT'"
            ).fetchone()
            seq = (seq_row["last_sequence"] + 1) if seq_row else 1
            conn.execute(
                "INSERT OR REPLACE INTO project_id_sequences (project_id, entity_type, last_sequence) VALUES ('__GLOBAL__', 'PROJECT', ?)",
                (seq,)
            )
            disp_id = f"PROJ-{seq:03d}"
            try:
                conn.execute(
                    "UPDATE projects SET display_id = ?, sequence_no = ? WHERE project_id = ?",
                    (disp_id, seq, project_id)
                )
            except Exception:
                pass
            return disp_id
        except Exception:
            return "PROJ-001"

    @classmethod
    def allocate_display_id(
        cls,
        conn: sqlite3.Connection,
        project_id: str,
        entity_type: str,
        plan_version: Optional[int] = None
    ) -> Tuple[str, str, int]:
        """
        Allocates the next sequence for (project_id, entity_type).
        Returns:
            (full_display_id, short_display_id, sequence_no)
        Example:
            ('PROJ-001-EVI-005', 'EVI-005', 5)
        """
        cls.ensure_sequence_table(conn)
        proj_disp = cls.get_project_display_id(conn, project_id) if project_id and project_id != "__GLOBAL__" else "GLOBAL"

        prefix = ENTITY_PREFIXES.get(entity_type.upper(), entity_type.upper())

        seq_row = conn.execute(
            "SELECT last_sequence FROM project_id_sequences WHERE project_id = ? AND entity_type = ?",
            (project_id or "__GLOBAL__", entity_type.upper())
        ).fetchone()
        seq = (seq_row["last_sequence"] + 1) if seq_row else 1

        conn.execute(
            "INSERT OR REPLACE INTO project_id_sequences (project_id, entity_type, last_sequence) VALUES (?, ?, ?)",
            (project_id or "__GLOBAL__", entity_type.upper(), seq)
        )

        short_id = f"{prefix}-{seq:03d}"
        if plan_version is not None and entity_type.upper() == "PLAN":
            full_id = f"{proj_disp}-{prefix}-{seq:03d}-V{plan_version}"
            short_id = f"{prefix}-{seq:03d}-V{plan_version}"
        elif proj_disp == "GLOBAL":
            full_id = short_id
        else:
            full_id = f"{proj_disp}-{prefix}-{seq:03d}"

        return full_id, short_id, seq


def run_database_schema_and_id_migration(db_path: str) -> Dict[str, Any]:
    """
    Applies column migrations to add display_id and sequence_no,
    and backfills existing database records with clean, persistent hierarchical IDs.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    IdService.ensure_sequence_table(conn)

    # 1. Add columns to relevant tables
    tables_to_migrate = [
        ("projects", "display_id TEXT", "sequence_no INTEGER"),
        ("runs", "display_id TEXT", "sequence_no INTEGER"),
        ("verification_plans", "display_id TEXT", "sequence_no INTEGER", "target_scope TEXT", "intent TEXT", "why_files_selected TEXT", "expected_output TEXT"),
        ("work_packages", "display_id TEXT", "sequence_no INTEGER", "proposal_reason TEXT", "risks TEXT", "why_proposed TEXT", "approval_status TEXT", "method TEXT", "tools TEXT", "agents TEXT", "expected_evidence TEXT", "target_files TEXT DEFAULT '[]'", "supporting_context TEXT DEFAULT '[]'", "excluded_paths TEXT DEFAULT '[]'"),
        ("verification_objectives", "display_id TEXT", "sequence_no INTEGER"),
        ("tasks", "display_id TEXT", "sequence_no INTEGER", "current_stage TEXT DEFAULT 'QUEUED'", "current_file TEXT", "current_function TEXT", "current_tool TEXT", "why_queued TEXT", "target_files TEXT DEFAULT '[]'", "supporting_context TEXT DEFAULT '[]'", "excluded_paths TEXT DEFAULT '[]'", "role_reason TEXT"),
        ("task_attempts", "display_id TEXT", "sequence_no INTEGER"),
        ("artifacts", "display_id TEXT", "sequence_no INTEGER"),
        ("evidence", "display_id TEXT", "sequence_no INTEGER", "duplicate_of_id TEXT", "line_range TEXT", "function_name TEXT", "observation TEXT", "expected_behavior TEXT"),
        ("findings", "display_id TEXT", "sequence_no INTEGER", "security_domain TEXT", "affected_component TEXT", "affected_files TEXT", "function_symbol TEXT", "line_range TEXT", "root_cause TEXT", "observed_behavior TEXT", "expected_behavior TEXT", "security_impact TEXT", "attack_scenario TEXT", "detection_method TEXT", "reproducer_spec TEXT", "validator_verdict TEXT", "plan_id TEXT", "plan_version TEXT", "work_package_id TEXT", "objective_id TEXT", "attempt_id TEXT", "parent_context_required INTEGER DEFAULT 0", "duplicate_of_id TEXT", "has_duplicates INTEGER DEFAULT 0", "poc_available INTEGER DEFAULT 0", "poc_command TEXT"),
        ("tool_executions", "display_id TEXT", "sequence_no INTEGER", "working_directory TEXT"),
        ("agents", "availability TEXT DEFAULT 'READY'", "auth_status TEXT DEFAULT 'AUTHENTICATED'", "supported_roles TEXT DEFAULT '[]'", "supported_methods TEXT DEFAULT '[]'", "supported_tools TEXT DEFAULT '[]'", "current_workload INTEGER DEFAULT 0", "last_execution_at TEXT", "current_task_id TEXT", "execution_policy TEXT DEFAULT 'STANDARD'")
    ]

    for tbl_def in tables_to_migrate:
        tbl = tbl_def[0]
        for col_def in tbl_def[1:]:
            col_name = col_def.split()[0]
            try:
                cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_def}")
            except Exception:
                pass

    # 2. Backfill Projects
    proj_rows = cursor.execute("SELECT project_id, created_at, display_id FROM projects ORDER BY created_at ASC").fetchall()
    migrated_counts = {"projects": 0, "plans": 0, "runs": 0, "wps": 0, "objs": 0, "tasks": 0, "evidence": 0, "findings": 0}

    for p in proj_rows:
        p_id = p["project_id"]
        disp_id = IdService.get_project_display_id(conn, p_id)
        migrated_counts["projects"] += 1

    # 3. Backfill Plans per project
    plan_rows = cursor.execute("SELECT plan_id, project_id, version, created_at, display_id FROM verification_plans ORDER BY created_at ASC").fetchall()
    for row in plan_rows:
        if not row["display_id"]:
            pid = row["project_id"] or "proj-legacy-unassigned"
            full_id, short_id, seq = IdService.allocate_display_id(conn, pid, "PLAN", row["version"])
            cursor.execute("UPDATE verification_plans SET display_id = ?, sequence_no = ? WHERE plan_id = ?", (full_id, seq, row["plan_id"]))
            migrated_counts["plans"] += 1

    # 4. Backfill WorkPackages
    wp_rows = cursor.execute("SELECT package_id, project_id, created_at, display_id FROM work_packages ORDER BY created_at ASC").fetchall()
    for row in wp_rows:
        if not row["display_id"]:
            pid = row["project_id"] or "proj-legacy-unassigned"
            full_id, short_id, seq = IdService.allocate_display_id(conn, pid, "WP")
            cursor.execute("UPDATE work_packages SET display_id = ?, sequence_no = ? WHERE package_id = ?", (full_id, seq, row["package_id"]))
            migrated_counts["wps"] += 1

    # 5. Backfill Objectives
    obj_rows = cursor.execute("SELECT objective_id, project_id, created_at, display_id FROM verification_objectives ORDER BY created_at ASC").fetchall()
    for row in obj_rows:
        if not row["display_id"]:
            pid = row["project_id"] or "proj-legacy-unassigned"
            full_id, short_id, seq = IdService.allocate_display_id(conn, pid, "OBJ")
            cursor.execute("UPDATE verification_objectives SET display_id = ?, sequence_no = ? WHERE objective_id = ?", (full_id, seq, row["objective_id"]))
            migrated_counts["objs"] += 1

    # 6. Backfill Runs
    run_rows = cursor.execute("SELECT run_id, project_id, start_time, display_id FROM runs ORDER BY start_time ASC").fetchall()
    for row in run_rows:
        if not row["display_id"]:
            pid = row["project_id"] or "proj-legacy-unassigned"
            full_id, short_id, seq = IdService.allocate_display_id(conn, pid, "RUN")
            cursor.execute("UPDATE runs SET display_id = ?, sequence_no = ? WHERE run_id = ?", (full_id, seq, row["run_id"]))
            migrated_counts["runs"] += 1

    # 7. Backfill Tasks
    task_rows = cursor.execute("SELECT task_id, project_id, created_at, display_id FROM tasks ORDER BY created_at ASC").fetchall()
    for row in task_rows:
        if not row["display_id"]:
            pid = row["project_id"] or "proj-legacy-unassigned"
            full_id, short_id, seq = IdService.allocate_display_id(conn, pid, "TASK")
            cursor.execute("UPDATE tasks SET display_id = ?, sequence_no = ? WHERE task_id = ?", (full_id, seq, row["task_id"]))
            migrated_counts["tasks"] += 1

    # 8. Backfill Evidence & Audit duplicates
    evi_rows = cursor.execute("""
        SELECT evidence_id, project_id, timestamp, display_id, command, raw_hash, duplicate_of_id
        FROM evidence ORDER BY timestamp ASC
    """).fetchall()

    seen_hashes = {}
    for row in evi_rows:
        pid = row["project_id"] or "proj-legacy-unassigned"
        raw_h = row["raw_hash"]
        dup_of = seen_hashes.get((pid, raw_h))

        if not row["display_id"]:
            full_id, short_id, seq = IdService.allocate_display_id(conn, pid, "EVI")
            cursor.execute(
                "UPDATE evidence SET display_id = ?, sequence_no = ?, duplicate_of_id = ? WHERE evidence_id = ?",
                (full_id, seq, dup_of, row["evidence_id"])
            )
            migrated_counts["evidence"] += 1
        elif dup_of and not row["duplicate_of_id"]:
            cursor.execute("UPDATE evidence SET duplicate_of_id = ? WHERE evidence_id = ?", (dup_of, row["evidence_id"]))

        if raw_h and (pid, raw_h) not in seen_hashes:
            seen_hashes[(pid, raw_h)] = row["display_id"] or full_id

    # 9. Backfill Findings
    vul_rows = cursor.execute("SELECT finding_id, project_id, created_at, display_id FROM findings ORDER BY created_at ASC").fetchall()
    for row in vul_rows:
        if not row["display_id"]:
            pid = row["project_id"] or "proj-legacy-unassigned"
            full_id, short_id, seq = IdService.allocate_display_id(conn, pid, "VUL")
            cursor.execute("UPDATE findings SET display_id = ?, sequence_no = ? WHERE finding_id = ?", (full_id, seq, row["finding_id"]))
            migrated_counts["findings"] += 1

    conn.commit()
    conn.close()

    return {
        "status": "MIGRATION_SUCCESS",
        "migrated_counts": migrated_counts
    }
