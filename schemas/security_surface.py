"""
LLMorch Data Contracts - Phase 7 Security Surface Model
Representing attack surfaces, trust boundaries, attacker capabilities, assets, and invariants.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class AttackerCapability(str, Enum):
    """Structured attacker threat model privilege taxonomy."""
    USER = "USER"
    GUEST = "GUEST"
    UNPRIVILEGED = "UNPRIVILEGED"
    PRIVILEGED = "PRIVILEGED"
    FIRMWARE = "FIRMWARE"
    PHYSICAL = "PHYSICAL"
    BUS_MASTER = "BUS_MASTER"
    DEVICE_LOCAL = "DEVICE_LOCAL"
    REMOTE = "REMOTE"
    UNKNOWN = "UNKNOWN"


class TrustBoundary(BaseModel):
    name: str
    from_domain: str
    to_domain: str
    description: str = ""


class EntryPoint(BaseModel):
    name: str
    interface_type: str  # bus_interface, MMIO, CLI, REST, DIF_API, syscall
    location: str
    attacker_capability: AttackerCapability = AttackerCapability.UNPRIVILEGED


class SecurityAsset(BaseModel):
    name: str
    asset_type: str  # key, memory_region, control_register, state
    location: str
    sensitivity: str = "HIGH"


class Countermeasure(BaseModel):
    name: str
    mechanism: str  # access_control, lock_bit, privilege_check, constant_time, assertions
    location: str
    effectiveness: str = "UNKNOWN"  # UNKNOWN until validated!


class SecuritySurface(BaseModel):
    """
    Typed data contract representing security architecture boundaries,
    assets, attacker capabilities, entry points, and invariants.
    """
    security_surface_id: str = Field(default_factory=lambda: f"sec-{uuid.uuid4().hex[:12]}")
    analysis_unit_id: Optional[str] = Field(default=None, description="Associated AnalysisUnit ID")
    repository_id: str = Field(default="", description="Parent repository ID")
    snapshot_id: str = Field(default="", description="Associated repository snapshot ID")
    assets: List[SecurityAsset] = Field(default_factory=list)
    boundaries: List[TrustBoundary] = Field(default_factory=list)
    attacker_capabilities: List[AttackerCapability] = Field(default_factory=list)
    privilege_tiers: List[str] = Field(default_factory=list)
    entry_points: List[EntryPoint] = Field(default_factory=list)
    states: List[str] = Field(default_factory=list)
    properties: List[str] = Field(default_factory=list)
    countermeasures: List[Countermeasure] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    schema_version: str = Field(default="1.0.0")
