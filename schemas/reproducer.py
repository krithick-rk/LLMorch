"""
LLMorch Data Contracts - Phase 8 Reproducer Model & State Machine
Enforces strict quarantine for model-generated harnesses and computes canonical manifest SHA-256.
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from pydantic import BaseModel, Field
import uuid


class ReproducerType(str, Enum):
    CRASH_REPRODUCER = "CRASH_REPRODUCER"
    FUZZ_SEED = "FUZZ_SEED"
    REGRESSION_TEST = "REGRESSION_TEST"
    FORMAL_COUNTEREXAMPLE = "FORMAL_COUNTEREXAMPLE"
    RTL_SIMULATION_STIMULUS = "RTL_SIMULATION_STIMULUS"
    SECURITY_PROPERTY_TEST = "SECURITY_PROPERTY_TEST"
    HW_SW_REPRODUCER = "HW_SW_REPRODUCER"


class ReproducerState(str, Enum):
    PROPOSED = "PROPOSED"
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    BUILDING = "BUILDING"
    BUILT = "BUILT"
    MINIMIZING = "MINIMIZING"
    MINIMIZED = "MINIMIZED"
    SANDBOXED = "SANDBOXED"
    READY_FOR_VALIDATION = "READY_FOR_VALIDATION"
    VALIDATING = "VALIDATING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    GENERATION_FAILED = "GENERATION_FAILED"
    SANDBOX_FAILED = "SANDBOX_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INVALIDATED = "INVALIDATED"


class Harness(BaseModel):
    """Execution harness wrapper (reused or generated)."""
    harness_id: str = Field(default_factory=lambda: f"harn-{uuid.uuid4().hex[:12]}")
    is_existing: bool = Field(default=False, description="Whether harness was reused from repository tests")
    source_provenance: Optional[str] = Field(default=None, description="Original file path or test suite reused")
    quarantined: bool = Field(default=True, description="True for all LLM-generated code until sandboxed")
    entry_file: str = Field(default="", description="Main harness entry file path")
    content: str = Field(default="", description="Source code of harness")
    raw_sha256: str = Field(default="", description="SHA-256 of raw harness content")

    @property
    def is_reused(self) -> bool:
        return self.is_existing


class ReproducerInput(BaseModel):
    """Input stimulus, payload, or property driving reproduction."""
    input_id: str = Field(default_factory=lambda: f"inp-{uuid.uuid4().hex[:12]}")
    input_type: str = Field(default="script", description="script, binary_payload, fuzz_seed, formal_property")
    data: str = Field(default="", description="Raw or encoded input data")
    raw_sha256: str = Field(default="", description="SHA-256 of input data")


class ReproducerManifest(BaseModel):
    """
    Immutable manifest defining reproducer execution boundary.
    Manifest SHA-256 is computed canonically with manifest_sha256 excluded from input.
    """
    reproducer_id: str = Field(default_factory=lambda: f"repro-{uuid.uuid4().hex[:12]}")
    candidate_id: str
    repository_snapshot_id: str = Field(default="snap-current")
    analysis_unit_id: Optional[str] = None
    domain: str = "software"
    reproducer_type: ReproducerType = ReproducerType.REGRESSION_TEST
    files: Union[List[str], Dict[str, str]] = Field(default_factory=list, description="Files included in package")
    artifact_hashes: Dict[str, Any] = Field(
        default_factory=dict,
        description="file -> hash string or dict with raw/canonical/semantic hashes"
    )
    build_command: Optional[str] = None
    build_commands: List[List[str]] = Field(default_factory=list, description="Build steps")
    run_command: str = ""
    run_commands: List[List[str]] = Field(default_factory=list, description="Execution steps")
    expected_failure: Union[str, Dict[str, Any]] = Field(default="", description="Expected failure assertion, exit code, or signal")
    required_tools: List[str] = Field(default_factory=list)
    tool_versions: Dict[str, str] = Field(default_factory=dict)
    environment_requirements: Dict[str, Any] = Field(default_factory=dict)
    sandbox_requirements: Dict[str, Any] = Field(default_factory=dict)
    requested_replay_count: int = 3
    determinism_declaration: str = "PROPOSED"
    minimization_metadata: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)
    manifest_sha256: Optional[str] = None

    def compute_canonical_hash(self) -> str:
        """
        Computes canonical SHA-256 of the manifest with manifest_sha256 excluded.
        Ensures immutable manifest identity for tamper detection.
        """
        data = self.model_dump()
        data.pop("manifest_sha256", None)
        canonical_json = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def seal(self) -> "ReproducerManifest":
        """Computes and locks the manifest_sha256 identity."""
        self.manifest_sha256 = self.compute_canonical_hash()
        return self

    def verify_integrity(self) -> bool:
        """Verifies that the manifest has not been tampered with."""
        if not self.manifest_sha256:
            return False
        return self.compute_canonical_hash() == self.manifest_sha256


class Reproducer(BaseModel):
    """
    Self-contained Reproducer Package.
    Quarantined until executed in sandbox and verified by the Validator.
    """
    reproducer_id: str = Field(default_factory=lambda: f"repro-{uuid.uuid4().hex[:12]}")
    candidate_id: str
    spec_id: str
    reproducer_type: ReproducerType = ReproducerType.REGRESSION_TEST
    state: ReproducerState = ReproducerState.PROPOSED
    manifest: ReproducerManifest
    harness: Optional[Harness] = None
    reproducer_input: Optional[ReproducerInput] = None
    inputs: List[ReproducerInput] = Field(default_factory=list)
    quarantined_files: List[str] = Field(default_factory=list)
    quarantine_path: str = Field(default="", description="Path in quarantined workspace")
    schema_version: str = Field(default="1.0.0")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def verify_tamper(self, files_on_disk: Optional[Dict[str, str]] = None) -> bool:
        """
        Verifies artifact hashes on disk against sealed manifest.
        Returns False if any file has been modified or manifest hash mismatch.
        """
        if not self.manifest.verify_integrity():
            return False

        if files_on_disk is not None:
            for fpath, exp in files_on_disk.items():
                if isinstance(self.manifest.artifact_hashes, dict):
                    actual_exp = self.manifest.artifact_hashes.get(fpath)
                    if isinstance(actual_exp, dict):
                        target_exp = actual_exp.get("raw") or actual_exp.get("raw_sha256")
                    else:
                        target_exp = actual_exp
                    if target_exp and exp != target_exp:
                        return False
            return True

        # Check files directly on filesystem
        file_list = []
        if isinstance(self.manifest.files, list):
            file_list.extend(self.manifest.files)
        elif isinstance(self.manifest.files, dict):
            file_list.extend(list(self.manifest.files.keys()))

        if not file_list and isinstance(self.manifest.artifact_hashes, dict):
            file_list.extend(list(self.manifest.artifact_hashes.keys()))

        for fpath in file_list:
            p = Path(fpath)
            if not p.exists():
                return False
            try:
                actual_h = hashlib.sha256(p.read_bytes()).hexdigest()
            except Exception:
                return False

            expected_h = None
            if isinstance(self.manifest.artifact_hashes, dict) and fpath in self.manifest.artifact_hashes:
                val = self.manifest.artifact_hashes[fpath]
                if isinstance(val, dict):
                    expected_h = val.get("raw") or val.get("raw_sha256")
                elif isinstance(val, str):
                    expected_h = val

            if expected_h is None and isinstance(self.manifest.files, dict):
                expected_h = self.manifest.files.get(fpath)

            if expected_h and actual_h != expected_h:
                return False

        return True
