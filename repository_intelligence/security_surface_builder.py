"""
LLMorch Repository Intelligence - Security Surface Builder (Phase 7)
Extracts security architecture boundaries, assets, attacker capabilities, entry points, and countermeasures.
"""

from typing import List, Dict, Any, Optional
from schemas.security_surface import (
    SecuritySurface,
    AttackerCapability,
    TrustBoundary,
    EntryPoint,
    SecurityAsset,
    Countermeasure,
)
from schemas.file_classification import FileClassificationRecord
from schemas.repository_intelligence import HW_SW_Contract


class SecuritySurfaceBuilder:
    """
    Constructs SecuritySurface representations for AnalysisUnits and repositories.
    """

    @classmethod
    def build_security_surface(
        cls,
        analysis_unit_id: str,
        repository_id: str,
        snapshot_id: str,
        scoped_files: List[FileClassificationRecord],
        contracts: List[HW_SW_Contract]
    ) -> SecuritySurface:
        assets: List[SecurityAsset] = []
        boundaries: List[TrustBoundary] = []
        entry_points: List[EntryPoint] = []
        countermeasures: List[Countermeasure] = []
        attacker_caps = [AttackerCapability.UNPRIVILEGED, AttackerCapability.USER]

        # Scan scoped files for security constructs
        for rec in scoped_files:
            rel_p = rec.rel_path
            low_p = rel_p.lower()

            # Entry Points
            if "api" in low_p or "ctrl" in low_p or "driver" in low_p or "bus" in low_p or "main" in low_p:
                entry_points.append(EntryPoint(
                    name=f"Interface: {rel_p}",
                    interface_type="MMIO_or_API",
                    location=rel_p,
                    attacker_capability=AttackerCapability.UNPRIVILEGED
                ))

            # Assets
            if "key" in low_p or "secret" in low_p or "priv" in low_p or "lock" in low_p or "token" in low_p:
                assets.append(SecurityAsset(
                    name=f"Asset in {rel_p}",
                    asset_type="control_register_or_key",
                    location=rel_p,
                    sensitivity="HIGH"
                ))

            # Countermeasures
            if "lock" in low_p or "racl" in low_p or "assert" in low_p or "check" in low_p or "guard" in low_p:
                countermeasures.append(Countermeasure(
                    name=f"Defense mechanism in {rel_p}",
                    mechanism="access_control_or_lock_bit",
                    location=rel_p,
                    effectiveness="UNKNOWN"
                ))

        # Integrate HW-SW Contract metadata
        for c in contracts:
            assets.append(SecurityAsset(
                name=f"Register: {c.register_name}",
                asset_type="control_register",
                location=c.hjson_ref or c.header_ref or "unknown",
                sensitivity="HIGH"
            ))
            if c.lock_bits:
                countermeasures.append(Countermeasure(
                    name=f"Lock bits for {c.register_name}: {c.lock_bits}",
                    mechanism="lock_bit_gating",
                    location=c.header_ref or "unknown",
                    effectiveness="UNKNOWN"
                ))

        # Trust Boundaries
        boundaries.append(TrustBoundary(
            name="Host/Firmware Trust Boundary",
            from_domain="Unprivileged Host",
            to_domain="Privileged Firmware/Hardware State",
            description="Access control boundary separating user operations from security register state."
        ))

        return SecuritySurface(
            analysis_unit_id=analysis_unit_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            assets=assets,
            boundaries=boundaries,
            attacker_capabilities=attacker_caps,
            privilege_tiers=["UNPRIVILEGED", "PRIVILEGED", "SECURE_WORLD"],
            entry_points=entry_points,
            states=["RESET", "OPERATIONAL", "DEBUG", "LOCKED"],
            properties=["Lock bits must be asserted prior to write enablement", "Access control checks must enforce privilege level"],
            countermeasures=countermeasures,
            assumptions=["Host software cannot bypass hardware lock bit gating without reset"],
            provenance={"builder": "SecuritySurfaceBuilder", "rule": "deterministic_metadata_scan"}
        )
