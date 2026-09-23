"""
LLMorch Data Contracts - Phase 7 Repository Intelligence Schemas
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class DependencyType(str, Enum):
    """Relation confidence type."""
    DIRECT = "DIRECT"
    INFERRED = "INFERRED"
    HEURISTIC = "HEURISTIC"
    HW_SW_CONTRACT = "HW_SW_CONTRACT"
    UNKNOWN = "UNKNOWN"


class ReachabilityStatus(str, Enum):
    """Reachability status from entry points."""
    REACHABLE = "REACHABLE"
    LIKELY_REACHABLE = "LIKELY_REACHABLE"
    POSSIBLY_REACHABLE = "POSSIBLY_REACHABLE"
    UNREACHABLE = "UNREACHABLE"
    UNKNOWN = "UNKNOWN"


class ExtendedRepositorySnapshot(BaseModel):
    """Rich metadata record representing a validated repository intake snapshot."""
    repository_id: str = Field(default_factory=lambda: f"repo-{uuid.uuid4().hex[:12]}")
    snapshot_id: str = Field(default_factory=lambda: f"snap-{uuid.uuid4().hex[:12]}")
    absolute_root: str = Field(..., description="Canonical absolute path to repository root")
    repository_type: str = Field(default="git", description="Repository type (git, directory, archive)")
    git_commit: Optional[str] = Field(default=None, description="Git commit hash if git repository")
    archive_hash: str = Field(..., description="Deterministic whole-repository archive hash")
    file_count: int = Field(default=0, description="Total analyzed file count")
    language_summary: Dict[str, int] = Field(default_factory=dict, description="File counts by language")
    build_systems: List[str] = Field(default_factory=list, description="Detected build systems (Bazel, FuseSoC, etc.)")
    metadata_systems: List[str] = Field(default_factory=list, description="Detected security metadata systems (HJSON, RACL, etc.)")
    symlink_summary: Dict[str, Any] = Field(default_factory=dict, description="Symlink audit results")
    classification_summary: Dict[str, int] = Field(default_factory=dict, description="File counts by classification")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    schema_version: str = Field(default="1.0.0")

    @property
    def source_path(self) -> str:
        return self.absolute_root


class BuildTarget(BaseModel):
    """Indexed build system target representation."""
    target_id: str = Field(default_factory=lambda: f"bt-{uuid.uuid4().hex[:12]}")
    build_system: str = Field(..., description="Bazel, FuseSoC, CMake, Cargo, etc.")
    target_name: str = Field(..., description="Canonical target name")
    defined_in_file: str = Field(..., description="Path to BUILD / .core / CMakeLists file")
    source_files: List[str] = Field(default_factory=list, description="Source files contained in target")
    dependencies: List[str] = Field(default_factory=list, description="Target dependency IDs or target names")
    output_artifacts: List[str] = Field(default_factory=list, description="Generated outputs")


class SymbolEntity(BaseModel):
    """Extracted program symbol or hardware module construct."""
    symbol_id: str = Field(default_factory=lambda: f"sym-{uuid.uuid4().hex[:12]}")
    name: str = Field(..., description="Symbol or module name")
    kind: str = Field(..., description="function, class, method, module, port, signal, always_block, register")
    language: str = Field(..., description="Language (c, cpp, go, java, python, rtl)")
    file_path: str = Field(..., description="Relative path of file containing symbol")
    line_start: int = Field(default=1)
    line_end: int = Field(default=1)
    parent_symbol_id: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DependencyRelation(BaseModel):
    """Deterministic dependency graph edge."""
    relation_id: str = Field(default_factory=lambda: f"dep-{uuid.uuid4().hex[:12]}")
    source_id: str = Field(..., description="Source file/symbol/target ID")
    target_id: str = Field(..., description="Target file/symbol/target ID")
    relation_type: DependencyType = Field(default=DependencyType.DIRECT)
    confidence: float = Field(default=1.0)
    provenance: str = Field(default="parser")


class HW_SW_Contract(BaseModel):
    """First-class HW ↔ SW contract model connecting RTL registers to C headers and DIF APIs."""
    contract_id: str = Field(default_factory=lambda: f"contract-{uuid.uuid4().hex[:12]}")
    register_name: str = Field(..., description="Register name (e.g. CTRL, PRIV_LOCK)")
    rtl_module: Optional[str] = Field(default=None, description="RTL module containing register")
    hjson_ref: Optional[str] = Field(default=None, description="Path to HJSON register description")
    header_ref: Optional[str] = Field(default=None, description="Generated C header file path")
    dif_ref: Optional[str] = Field(default=None, description="DIF firmware driver path")
    access_policy: Optional[str] = Field(default=None, description="Access permissions (RW, RO, WO)")
    lock_bits: List[str] = Field(default_factory=list, description="Associated lock bit signals")


class SecretQuarantineRecord(BaseModel):
    """Audit record for quarantined secrets and key material."""
    quarantine_id: str = Field(default_factory=lambda: f"secq-{uuid.uuid4().hex[:12]}")
    file_path: str = Field(..., description="Repository path containing secret")
    secret_type: str = Field(..., description="API_KEY, PRIVATE_KEY, PASSWORD, TOKEN, CERTIFICATE")
    redacted_preview: str = Field(..., description="Safe redacted string preview")
    quarantined_at: datetime = Field(default_factory=datetime.utcnow)


class ContextExpansionRecord(BaseModel):
    """Audit record capturing requested and approved agent context expansion."""
    expansion_id: str = Field(default_factory=lambda: f"exp-{uuid.uuid4().hex[:12]}")
    analysis_unit_id: str = Field(..., description="Primary AnalysisUnit ID")
    requesting_agent_id: str = Field(..., description="Agent ID requesting context expansion")
    reason: str = Field(..., description="Reason for expansion (e.g. missing dependency foo.h)")
    expanded_paths: List[str] = Field(default_factory=list, description="Approved additional file paths")
    status: str = Field(default="ALLOWED", description="ALLOWED or BLOCKED")
    created_at: datetime = Field(default_factory=datetime.utcnow)
