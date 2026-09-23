"""
LLMorch Data Contracts - Phase 7 File Classification & Symlink Schemas
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class FileClassificationType(str, Enum):
    """Deterministic file classification categories."""
    PRIMARY_SOURCE = "PRIMARY_SOURCE"
    BUILD_METADATA = "BUILD_METADATA"
    SECURITY_METADATA = "SECURITY_METADATA"
    GENERATED = "GENERATED"
    VENDOR = "VENDOR"
    THIRD_PARTY = "THIRD_PARTY"
    TEST = "TEST"
    FORMAL = "FORMAL"
    DOCUMENTATION = "DOCUMENTATION"
    SCRIPT = "SCRIPT"
    CONFIGURATION = "CONFIGURATION"
    CACHE = "CACHE"
    BUILD_OUTPUT = "BUILD_OUTPUT"
    NOISE = "NOISE"
    SECRET = "SECRET"
    UNKNOWN = "UNKNOWN"


class SymlinkStatus(str, Enum):
    """Symlink safety classification."""
    INTERNAL_VALID = "INTERNAL_VALID"
    EXTERNAL_BLOCKED = "EXTERNAL_BLOCKED"
    BROKEN = "BROKEN"


class SymlinkRecord(BaseModel):
    """Audit record for symlinks within or pointing outside repository boundaries."""
    symlink_path: str = Field(..., description="Repository path of the symlink")
    target_path: str = Field(..., description="Resolved target path")
    status: SymlinkStatus = Field(..., description="Symlink status classification")
    is_external: bool = Field(..., description="True if target is outside authorized root")


class FileClassificationRecord(BaseModel):
    """Per-file classification record with provenance and identity hashes."""
    file_id: str = Field(default_factory=lambda: f"file-{uuid.uuid4().hex[:12]}")
    rel_path: str = Field(..., description="Relative path from repository root")
    abs_path: str = Field(..., description="Absolute file path")
    content_hash: str = Field(..., description="SHA-256 content hash")
    classification: FileClassificationType = Field(..., description="Primary classification type")
    language: str = Field(default="unknown", description="Programming or markup language")
    size_bytes: int = Field(default=0, description="File size in bytes")
    is_symlink: bool = Field(default=False, description="True if symlink")
    is_secret: bool = Field(default=False, description="True if secret key or credential detected")
    target_ref: Optional[str] = Field(default=None, description="If generated, source specification path")
    created_at: datetime = Field(default_factory=datetime.utcnow)
