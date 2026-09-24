"""
LLMorch Data Contracts - Artifact Model
"""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid


class ArtifactType(str, Enum):
    """Classification of generated execution artifacts."""
    CODE = "CODE"
    PATCH = "PATCH"
    LOG = "LOG"
    REPORT = "REPORT"
    EVIDENCE = "EVIDENCE"
    TEST_CASE = "TEST_CASE"
    REPRODUCER = "REPRODUCER"
    SECURITY_SURFACE = "SECURITY_SURFACE"
    ANALYSIS_UNIT = "ANALYSIS_UNIT"
    OTHER = "OTHER"


class RetentionClass(str, Enum):
    """Artifact lifecycle and retention policy."""
    TEMPORARY = "TEMPORARY"
    TASK = "TASK"
    WORKFLOW = "WORKFLOW"
    PERMANENT = "PERMANENT"


class Artifact(BaseModel):
    """
    Representation of a stored output artifact.
    Artifacts refer to actual stored files or external objects.
    """
    artifact_id: str = Field(default_factory=lambda: f"art-{uuid.uuid4().hex[:12]}", description="Unique artifact identifier")
    task_id: str = Field(..., description="Associated task identifier")
    run_id: Optional[str] = Field(default=None, description="Run attempt identifier that produced the artifact")
    type: ArtifactType = Field(default=ArtifactType.OTHER, description="Type classification of the artifact")
    uri_or_path: str = Field(..., description="File path or URI location of stored artifact object")
    mime_type: str = Field(default="application/octet-stream", description="MIME content type")
    sha256: str = Field(..., description="SHA-256 hash digest of content")
    size: int = Field(..., description="Content size in bytes")
    producer: str = Field(..., description="Identity of producer (agent_id or tool_id)")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Derivation tree and environment metadata")
    retention_class: RetentionClass = Field(default=RetentionClass.TASK, description="Retention policy class")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Artifact creation timestamp")
