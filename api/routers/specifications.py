"""
LLMorch API — Specifications Router
Endpoints for specification document ingestion and structured requirement browsing.
"""

from __future__ import annotations

from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.session import require_session, SessionInfo
from history.database import get_db_path, DatabaseService
from history.soc_repositories import SpecificationRepository, RequirementRepository
from specifications.ingest import SpecificationIngestor


router = APIRouter(prefix="/api/specifications", tags=["specifications"])


def _get_db() -> DatabaseService:
    return DatabaseService(get_db_path())


class SpecificationIngestRequest(BaseModel):
    file_path: str
    title: Optional[str] = None
    doc_type: Optional[str] = None
    version: Optional[str] = None


@router.post("/ingest")
def ingest_specification(
    req: SpecificationIngestRequest,
    session: SessionInfo = Depends(require_session)
):
    """Ingests a TRM/RM or Markdown specification file, extracting structured requirements."""
    p = Path(req.file_path).resolve()
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=400, detail=f"File not found: {req.file_path}")

    try:
        res = SpecificationIngestor.ingest_file(str(p), req.title)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    spec = res["specification"]
    requirements = res["requirements"]

    db = _get_db()
    spec_repo = SpecificationRepository(db)
    req_repo = RequirementRepository(db)

    spec_repo.save(spec)
    for r in requirements:
        req_repo.save(r)

    return {
        "status": "INGESTED",
        "specification": spec.model_dump(),
        "requirements_count": len(requirements),
        "extracted_claims_count": len(res["claims"]),
        "assumptions_count": len(res["assumptions"]),
        "sample_requirements": [r.model_dump() for r in requirements[:5]]
    }


@router.get("")
def list_specifications(
    session: SessionInfo = Depends(require_session)
):
    """Lists all ingested specifications."""
    db = _get_db()
    spec_repo = SpecificationRepository(db)
    specs = spec_repo.list_all()
    return {"specifications": [s.model_dump() for s in specs], "total": len(specs)}


@router.get("/{spec_id}/requirements")
def list_spec_requirements(
    spec_id: str,
    session: SessionInfo = Depends(require_session)
):
    """Lists requirements extracted from a specific specification."""
    db = _get_db()
    req_repo = RequirementRepository(db)
    reqs = req_repo.list_for_spec(spec_id)
    return {"spec_id": spec_id, "requirements": [r.model_dump() for r in reqs], "total": len(reqs)}
