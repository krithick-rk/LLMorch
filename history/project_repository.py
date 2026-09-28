"""
LLMorch Persistence — Project Repository & Isolation Model
Supports first-class project workspace management, project switching,
and project-local vs global intelligence isolation.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from history.database import DatabaseService


class ProjectRepository:
    """Persistent storage and lifecycle for isolated LLMorch engineering projects."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service
        self._ensure_table()
        self._seed_defaults_if_empty()

    def _ensure_table(self) -> None:
        with self.db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    target_directory TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'INITIALIZED',
                    is_active INTEGER NOT NULL DEFAULT 0,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            try:
                conn.execute("ALTER TABLE tasks ADD COLUMN project_id TEXT")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE runs ADD COLUMN project_id TEXT")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE analyst_questions ADD COLUMN project_id TEXT")
            except Exception:
                pass
            conn.commit()

    def _next_untitled_name(self) -> str:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT name FROM projects WHERE name LIKE 'Untitled Project %'").fetchall()
            max_num = 0
            for r in rows:
                name = r["name"] if isinstance(r, dict) or hasattr(r, "__getitem__") else r[0]
                parts = str(name).split("Untitled Project ")
                if len(parts) == 2 and parts[1].isdigit():
                    max_num = max(max_num, int(parts[1]))
            return f"Untitled Project {max_num + 1:03d}"

    def _seed_defaults_if_empty(self) -> None:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            count = cursor.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            if count == 0:
                now = datetime.now(timezone.utc).isoformat()
                defaults = [
                    (
                        "proj-opentitan-01",
                        "OpenTitan Security Review",
                        "/home/hackdac/Desktop/intern/LLMorch",
                        "READY",
                        1,
                        json.dumps({
                            "classification": "SoC Verification & Security Root of Trust",
                            "rtl_files": 428,
                            "c_files": 186,
                            "py_files": 72,
                            "spec_count": 13,
                            "build_system": "Bazel / Meson / FuseSoC",
                            "readiness": "READY_FOR_VERIFICATION"
                        }),
                        now,
                        now,
                    ),
                    (
                        "proj-caliptra-01",
                        "Caliptra Analysis",
                        "/tmp/caliptra",
                        "INITIALIZED",
                        0,
                        json.dumps({
                            "classification": "Hardware Root of Trust Subsystem",
                            "rtl_files": 142,
                            "c_files": 45,
                            "py_files": 12,
                            "spec_count": 4,
                            "build_system": "Make / Cargo",
                            "readiness": "PENDING_INTAKE"
                        }),
                        now,
                        now,
                    ),
                    (
                        "proj-untitled-001",
                        "Untitled Project 001",
                        "/tmp/test",
                        "INITIALIZED",
                        0,
                        json.dumps({
                            "classification": "Generic Software Directory",
                            "rtl_files": 0,
                            "c_files": 1,
                            "py_files": 1,
                            "spec_count": 0,
                            "build_system": "Not detected",
                            "readiness": "WAITING_FOR_USER_ACTION"
                        }),
                        now,
                        now,
                    ),
                ]
                cursor.executemany("""
                    INSERT INTO projects (
                        project_id, name, target_directory, status, is_active, metadata, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, defaults)
                conn.commit()

    def create_project(
        self,
        name: Optional[str] = None,
        target_directory: str = "/tmp/test",
        status: str = "INITIALIZED",
        metadata: Optional[Dict[str, Any]] = None,
        set_active: bool = True,
    ) -> Dict[str, Any]:
        p_name = (name or "").strip()
        if not p_name:
            p_name = self._next_untitled_name()

        target_dir = str(target_directory or "").strip()
        if not target_dir:
            target_dir = "/tmp/test"

        now = datetime.now(timezone.utc).isoformat()
        project_id = f"proj-{uuid.uuid4().hex[:8]}"

        meta = dict(metadata or {})

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if set_active:
                cursor.execute("UPDATE projects SET is_active = 0")

            cursor.execute("""
                INSERT INTO projects (
                    project_id, name, target_directory, status, is_active, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                p_name,
                target_dir,
                status,
                1 if set_active else 0,
                json.dumps(meta),
                now,
                now,
            ))
            conn.commit()

        return self.get_project(project_id) or {
            "project_id": project_id,
            "name": p_name,
            "target_directory": target_dir,
            "status": status,
            "is_active": set_active,
            "metadata": meta,
            "created_at": now,
            "updated_at": now,
        }

    def list_projects(self, include_archived: bool = False) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT project_id, name, target_directory, status, is_active, metadata, created_at, updated_at
                FROM projects
            """
            if not include_archived:
                query += " WHERE status != 'ARCHIVED'"
            query += " ORDER BY is_active DESC, updated_at DESC"

            rows = cursor.execute(query).fetchall()

            result = []
            for r in rows:
                meta = {}
                try:
                    meta = json.loads(r["metadata"]) if r["metadata"] else {}
                except Exception:
                    pass
                result.append({
                    "project_id": r["project_id"],
                    "name": r["name"],
                    "target_directory": r["target_directory"],
                    "status": r["status"],
                    "is_active": bool(r["is_active"]),
                    "metadata": meta,
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                })
            return result

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            r = cursor.execute("""
                SELECT project_id, name, target_directory, status, is_active, metadata, created_at, updated_at
                FROM projects
                WHERE project_id = ?
            """, (project_id,)).fetchone()
            if not r:
                return None
            meta = {}
            try:
                meta = json.loads(r["metadata"]) if r["metadata"] else {}
            except Exception:
                pass
            return {
                "project_id": r["project_id"],
                "name": r["name"],
                "target_directory": r["target_directory"],
                "status": r["status"],
                "is_active": bool(r["is_active"]),
                "metadata": meta,
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }

    def get_active_project(self) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            r = cursor.execute("""
                SELECT project_id, name, target_directory, status, is_active, metadata, created_at, updated_at
                FROM projects
                WHERE is_active = 1 AND status != 'ARCHIVED'
                ORDER BY updated_at DESC
                LIMIT 1
            """).fetchone()
            if not r:
                all_p = self.list_projects(include_archived=False)
                if all_p:
                    self.set_active_project(all_p[0]["project_id"])
                    return all_p[0]
                return None
            meta = {}
            try:
                meta = json.loads(r["metadata"]) if r["metadata"] else {}
            except Exception:
                pass
            return {
                "project_id": r["project_id"],
                "name": r["name"],
                "target_directory": r["target_directory"],
                "status": r["status"],
                "is_active": True,
                "metadata": meta,
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }

    def get_active_project_id(self) -> Optional[str]:
        act = self.get_active_project()
        return act["project_id"] if act else None

    def set_active_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE projects SET is_active = 0")
            cursor.execute("""
                UPDATE projects
                SET is_active = 1, updated_at = ?
                WHERE project_id = ?
            """, (now, project_id))
            conn.commit()
        return self.get_project(project_id)

    def archive_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE projects
                SET status = 'ARCHIVED', is_active = 0, updated_at = ?
                WHERE project_id = ?
            """, (now, project_id))
            conn.commit()

        # If we archived the active project, activate another non-archived project
        active = self.get_active_project()
        if not active:
            candidates = self.list_projects(include_archived=False)
            if candidates:
                self.set_active_project(candidates[0]["project_id"])

        return self.get_project(project_id)

    def update_project(self, project_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        existing = self.get_project(project_id)
        if not existing:
            return None

        now = datetime.now(timezone.utc).isoformat()
        name = kwargs.get("name", existing["name"])
        target_directory = kwargs.get("target_directory", existing["target_directory"])
        status = kwargs.get("status", existing["status"])
        meta = existing.get("metadata", {})
        if "metadata" in kwargs:
            meta.update(kwargs["metadata"])

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE projects
                SET name = ?, target_directory = ?, status = ?, metadata = ?, updated_at = ?
                WHERE project_id = ?
            """, (name, target_directory, status, json.dumps(meta), now, project_id))
            conn.commit()

        return self.get_project(project_id)

    def get_project_summary(self, project_id: str) -> Dict[str, Any]:
        """Calculates project-scoped counts and runtime execution state strictly for project_id."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            task_count = cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_id = ?", (project_id,)).fetchone()[0]
            active_tasks = cursor.execute(
                "SELECT COUNT(*) FROM tasks WHERE project_id = ? AND status IN ('RUNNING','IN_PROGRESS','ANALYZING')",
                (project_id,)
            ).fetchone()[0]
            run_count = cursor.execute("SELECT COUNT(*) FROM runs WHERE project_id = ?", (project_id,)).fetchone()[0]
            decision_count = cursor.execute("SELECT COUNT(*) FROM questions WHERE project_id = ?", (project_id,)).fetchone()[0]
            open_decisions = cursor.execute(
                "SELECT COUNT(*) FROM questions WHERE project_id = ? AND status = 'QUESTION_PENDING'",
                (project_id,)
            ).fetchone()[0]
            finding_count = cursor.execute("SELECT COUNT(*) FROM findings WHERE project_id = ?", (project_id,)).fetchone()[0]
            evidence_count = cursor.execute("SELECT COUNT(*) FROM evidence WHERE project_id = ?", (project_id,)).fetchone()[0]
            gap_count = cursor.execute("SELECT COUNT(*) FROM gaps WHERE project_id = ?", (project_id,)).fetchone()[0]
            plan_count = cursor.execute("SELECT COUNT(*) FROM verification_plans WHERE project_id = ?", (project_id,)).fetchone()[0]

            # Fetch active run for this project strictly
            active_run_row = cursor.execute("""
                SELECT * FROM runs
                WHERE project_id = ? AND run_state IN ('RUNNING','PAUSE_REQUESTED','PAUSED','RESUME_REQUESTED','WAITING_FOR_ANALYST','REPOSITORY_ANALYSIS')
                ORDER BY start_time DESC LIMIT 1
            """, (project_id,)).fetchone()

            runtime_state = "IDLE"
            elapsed_seconds = 0.0
            run_id = None
            if active_run_row:
                ar = dict(active_run_row)
                run_id = ar.get("run_id")
                runtime_state = ar.get("run_state") or ar.get("status") or "RUNNING"
                analysis_start = ar.get("analysis_started_at")
                if analysis_start and runtime_state == "RUNNING":
                    try:
                        st = datetime.fromisoformat(str(analysis_start).replace("Z", "+00:00"))
                        elapsed_seconds = max(0.0, (datetime.now(timezone.utc) - st).total_seconds())
                    except Exception:
                        elapsed_seconds = float(ar.get("active_duration_seconds") or 0.0)
                else:
                    elapsed_seconds = float(ar.get("active_duration_seconds") or 0.0)

            return {
                "project_id": project_id,
                "tasks": task_count,
                "active_tasks": active_tasks,
                "runs": run_count,
                "decisions": decision_count,
                "open_decisions": open_decisions,
                "findings": finding_count,
                "evidence": evidence_count,
                "gaps": gap_count,
                "verification_plans": plan_count,
                "runtime_state": runtime_state,
                "elapsed_seconds": int(elapsed_seconds),
                "active_run_id": run_id,
            }
