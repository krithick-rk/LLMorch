"""
LLMorch Data Contracts - Evidence Model
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid


class EvidenceSourceType(str, Enum):
    """Source classification for recorded evidence."""
    AGENT_CLAIM = "AGENT_CLAIM"
    TOOL_OUTPUT = "TOOL_OUTPUT"
    EXECUTION_RESULT = "EXECUTION_RESULT"
    VALIDATOR_RESULT = "VALIDATOR_RESULT"


class Evidence(BaseModel):
    """
    Representation of objective evidence recorded during execution.
    Distinguishes agent claims from tool execution and validator results.
    Never treat an LLM statement itself as proof.
    """
    evidence_id: str = Field(default_factory=lambda: f"evd-{uuid.uuid4().hex[:12]}", description="Unique evidence identifier")
    task_id: str = Field(..., description="Associated task identifier")
    run_id: str = Field(..., description="Associated run attempt identifier")
    agent_id: str = Field(..., description="Identifier of agent associated with evidence recording")
    artifact_id: Optional[str] = Field(default=None, description="Optional associated artifact identifier")
    source_type: EvidenceSourceType = Field(..., description="Source classification")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp evidence was recorded")
    tool: Optional[str] = Field(default=None, description="Tool name if tool output")
    command: Optional[str] = Field(default=None, description="Exact command string executed")
    raw_hash: str = Field(..., description="Hash digest of raw unparsed output")
    canonical_hash: str = Field(..., description="Hash digest of normalized canonical representation")
    semantic_fingerprint: str = Field(..., description="Semantic representation fingerprint")
    environment_fingerprint: str = Field(..., description="Execution environment fingerprint")
    exit_status: Optional[int] = Field(default=None, description="Process exit code if command execution")
    provenance_links: List[str] = Field(default_factory=list, description="Identifiers of preceding evidence/artifacts")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
