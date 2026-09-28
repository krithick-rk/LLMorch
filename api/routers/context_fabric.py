"""
LLMorch API — SoC Context Fabric Router
Provides graph summaries and task-scoped context packs connecting specifications, RTL, and interfaces.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService
from history.phase9_repositories import TargetRepositoryRepository
from history.soc_repositories import RequirementRepository
from context_fabric.fabric import SoCContextFabric
from schemas.soc_ontology import SoCBucket
from schemas.soc_verification import SoCComponent, InterfaceContract, SecurityAsset


router = APIRouter(prefix="/api/context-fabric", tags=["context-fabric"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


@router.get("/summary")
def get_context_fabric_summary(
    session: SessionInfo = Depends(require_session)
):
    """Retrieves full SoC Context Fabric summary and graph components."""
    db = _get_db()
    target_repo = TargetRepositoryRepository(db)
    cur = target_repo.get_current()
    repo_path = cur["repository_path"] if cur else "/unknown"

    fabric = SoCContextFabric(repo_path)
    # Populate from SQLite if components exist
    with db.get_connection() as conn:
        comp_rows = conn.execute("SELECT * FROM soc_components").fetchall()
        for r in comp_rows:
            d = dict(r)
            fabric.add_component(SoCComponent(
                component_id=d["component_id"],
                name=d["name"],
                component_type=d["component_type"],
                clock_domain=d.get("clock_domain"),
                reset_domain=d.get("reset_domain"),
                power_domain=d.get("power_domain"),
                security_tier=d.get("security_tier", "STANDARD")
            ))

    req_repo = RequirementRepository(db)
    for req in req_repo.list_all(limit=50):
        fabric.add_requirement(req)

    return fabric.export_graph_summary()


@router.get("/pack/{task_id}")
def get_task_context_pack(
    task_id: str,
    session: SessionInfo = Depends(require_session)
):
    """Retrieves task-specific token-bounded context pack."""
    db = _get_db()
    with db.get_connection() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    d = dict(task)
    bucket_val = d.get("bucket") or "security"
    soc_b = SoCBucket(bucket_val) if bucket_val in [b.value for b in SoCBucket] else SoCBucket.SECURITY

    fabric = SoCContextFabric(d.get("scope") or "source/")
    pack = fabric.assemble_context_pack(
        task_id=task_id,
        role=d.get("role") or "general_analysis",
        bucket=soc_b,
        scope=d.get("scope") or "source/"
    )
    return pack.model_dump()
