"""
LLMorch Data Contracts - Phase 8 ReproSpec Model
Structured specification of reproduction preconditions, triggers, harnesses, and validation signals.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid

from schemas.reproducer import ReproducerType


class ReproSpec(BaseModel):
    """
    Specification for reproducible vulnerability demonstration.
    Serves as blueprint for the Reproducer Generation Engine.
    """
    spec_id: str = Field(default_factory=lambda: f"spec-{uuid.uuid4().hex[:12]}", description="Unique ReproSpec ID")
    candidate_id: str = Field(..., description="Target candidate hypothesis ID")
    objective: str = Field(..., description="Reproducer objective statement")
    domain: str = Field(default="software", description="Target domain: c, rust, python, rtl, formal, hw_sw")
    reproducer_type: ReproducerType = Field(default=ReproducerType.REGRESSION_TEST, description="Selected strategy")
    preconditions: Union[List[str], Dict[str, Any]] = Field(default_factory=list, description="Preconditions")
    required_preconditions: List[str] = Field(default_factory=list, description="State preconditions for triggering")
    entry_point: str = Field(default="", description="Target function, method, signal, or CLI entry point")
    trigger: str = Field(default="", description="Action or input sequence that triggers hypothesized behavior")
    expected_failure: Union[str, Dict[str, Any]] = Field(default="", description="Expected failure signal (assertion, crash, register mismatch)")
    required_harness: Union[str, Dict[str, Any]] = Field(default="existing_or_generated", description="Harness strategy descriptor")
    required_tools: List[str] = Field(default_factory=list, description="Toolchain requirements (gcc, pytest, verilator, z3)")
    build_procedure: Union[str, List[str]] = Field(default_factory=list, description="Commands to build test package")
    run_procedure: Union[str, List[str]] = Field(default_factory=list, description="Commands to execute reproducer")
    validation_signal: str = Field(default="deterministic_signal", description="Deterministic pattern or condition confirming reproduction")
    requested_replay_count: int = Field(default=3, description="Number of replays requested for determinism check")
    environment_requirements: Dict[str, Any] = Field(default_factory=dict, description="OS/tool version constraints")
    limitations: List[str] = Field(default_factory=list, description="Known limitations or assumptions")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Spec creation timestamp")
