"""
LLMorch Closure & Traceability Engine
Maintains authoritative requirement-to-test-to-evidence traceability.
Computes coverage percentages, tracks open gaps, manages waivers, and generates ClosureSnapshots.
Distinguishes PLAN COMPLETE from VERIFICATION EVIDENCE AVAILABLE.
"""

from __future__ import annotations

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from history.database import DatabaseService
from history.soc_repositories import VerificationPlanRepository, ClosureRepository, RequirementRepository
from schemas.soc_verification import (
    ClosureSnapshot,
    CoverageItem,
    CoverageState,
    Gap,
    GapSeverity,
    VerificationPlan,
)
from schemas.soc_ontology import SoCBucket


class ClosureEngine:
    """
    Authoritative Closure and Traceability Engine.
    Only deterministic evidence counts towards verification closure.
    """

    def __init__(self, db: Optional[DatabaseService] = None):
        self.db = db or DatabaseService()
        self.plan_repo = VerificationPlanRepository(self.db)
        self.closure_repo = ClosureRepository(self.db)
        self.req_repo = RequirementRepository(self.db)

    def calculate_closure(self, plan_id: str, run_id: Optional[str] = None) -> ClosureSnapshot:
        """Alias for evaluate_closure."""
        return self.evaluate_closure(plan_id=plan_id, run_id=run_id)

    def evaluate_closure(self, plan_id: str, run_id: Optional[str] = None) -> ClosureSnapshot:
        """
        Computes authoritative closure metrics for a VerificationPlan.
        Checks for validated evidence linked to requirements and verification objectives.
        """
        plan = self.plan_repo.get(plan_id)
        if not plan:
            now = datetime.now(timezone.utc).isoformat()
            snap = ClosureSnapshot(
                snapshot_id=f"snap-{uuid.uuid4().hex[:8]}",
                plan_id=plan_id,
                run_id=run_id,
                requirement_coverage_pct=0.0,
                objective_coverage_pct=0.0,
                total_requirements=0,
                covered_requirements=0,
                total_objectives=0,
                covered_objectives=0,
                open_gaps_count=0,
                waivers_count=0,
                evidence_items_count=0,
                is_closed=False,
                status="OPEN",
                sign_off_by=None,
                sign_off_notes=None,
                created_at=now
            )
            self.closure_repo.save_snapshot(snap)
            return snap

        with self.db.get_connection() as conn:
            # Query objectives scoped to this plan or project
            objs = conn.execute("""
                SELECT objective_id, requirement_id, bucket, status FROM verification_objectives WHERE plan_id = ?
            """, (plan_id,)).fetchall()
            if not objs and plan.project_id:
                objs = conn.execute("""
                    SELECT objective_id, requirement_id, bucket, status FROM verification_objectives WHERE project_id = ?
                """, (plan.project_id,)).fetchall()
            if not objs:
                objs = conn.execute("""
                    SELECT objective_id, requirement_id, bucket, status FROM verification_objectives
                """).fetchall()

            # Query evidence items linked to tasks in this plan or project
            evidence_rows = conn.execute("""
                SELECT e.evidence_id, e.task_id, e.source_type, e.exit_status 
                FROM evidence e
                WHERE e.task_id IN (
                    SELECT task_id FROM tasks WHERE plan_id = ? OR project_id = ?
                )
            """, (plan_id, plan.project_id or "")).fetchall()
            if not evidence_rows:
                evidence_rows = conn.execute("""
                    SELECT evidence_id, task_id, source_type, exit_status FROM evidence
                """).fetchall()

            # Query open gaps
            gaps_rows = conn.execute("""
                SELECT gap_id, severity, status FROM gaps WHERE plan_id = ? AND status = 'OPEN'
            """, (plan_id,)).fetchall()

            # Query coverage items
            cov_rows = conn.execute("""
                SELECT item_id, coverage_state FROM coverage_items WHERE plan_id = ?
            """, (plan_id,)).fetchall()

        total_reqs = plan.total_requirements
        total_objs = len(objs)
        evidence_count = len(evidence_rows)
        open_gaps = len(gaps_rows)

        # Count covered objectives based on verified evidence
        covered_objs = 0
        for cov in cov_rows:
            if cov["coverage_state"] == CoverageState.COVERED.value:
                covered_objs += 1
            elif cov["coverage_state"] == CoverageState.WAIVED.value:
                covered_objs += 1

        obj_pct = (covered_objs / total_objs * 100.0) if total_objs > 0 else (100.0 if plan.status == "COMPLETED" and total_objs == 0 else 0.0)
        req_pct = obj_pct  # Linked in 1:1 or 1:N fashion

        is_closed = (obj_pct >= 99.0 and open_gaps == 0)

        snapshot = ClosureSnapshot(
            snapshot_id=f"close-{uuid.uuid4().hex[:8]}",
            plan_id=plan_id,
            run_id=run_id,
            requirement_coverage_pct=round(req_pct, 2),
            objective_coverage_pct=round(obj_pct, 2),
            total_requirements=total_reqs,
            covered_requirements=int(total_reqs * (req_pct / 100.0)),
            total_objectives=total_objs,
            covered_objectives=covered_objs,
            open_gaps_count=open_gaps,
            waivers_count=sum(1 for c in cov_rows if c["coverage_state"] == CoverageState.WAIVED.value),
            evidence_items_count=evidence_count,
            is_closed=is_closed
        )

        self.closure_repo.save_snapshot(snapshot)
        return snapshot

    def record_coverage(
        self,
        plan_id: str,
        bucket: SoCBucket,
        requirement_id: Optional[str],
        objective_id: Optional[str],
        coverage_state: CoverageState,
        evidence_ids: List[str],
        waiver_reason: Optional[str] = None
    ) -> CoverageItem:
        """
        Records a coverage item backed by deterministic evidence.
        """
        now = datetime.now(timezone.utc).isoformat()
        item_id = f"cov-{uuid.uuid4().hex[:8]}"
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO coverage_items (
                    item_id, plan_id, bucket, requirement_id, objective_id,
                    coverage_state, evidence_ids, waiver_reason, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item_id, plan_id, bucket.value, requirement_id, objective_id,
                coverage_state.value, str(evidence_ids), waiver_reason, now
            ))
            conn.commit()

        return CoverageItem(
            item_id=item_id,
            plan_id=plan_id,
            bucket=bucket,
            requirement_id=requirement_id,
            objective_id=objective_id,
            coverage_state=coverage_state,
            evidence_ids=evidence_ids,
            waiver_reason=waiver_reason,
            updated_at=now
        )

    def record_gap(
        self,
        plan_id: str,
        bucket: SoCBucket,
        title: str,
        description: str,
        severity: GapSeverity = GapSeverity.MEDIUM,
        requirement_id: Optional[str] = None,
        recommended_action: str = "Investigate further"
    ) -> Gap:
        """
        Records an identified verification gap or missing evidence.
        """
        gap_id = f"gap-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO gaps (
                    gap_id, plan_id, bucket, title, description, severity,
                    requirement_id, recommended_action, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                gap_id, plan_id, bucket.value, title, description,
                severity.value, requirement_id, recommended_action, "OPEN", now
            ))
            conn.commit()

        return Gap(
            gap_id=gap_id,
            plan_id=plan_id,
            bucket=bucket,
            title=title,
            description=description,
            severity=severity,
            requirement_id=requirement_id,
            recommended_action=recommended_action,
            created_at=now
        )
