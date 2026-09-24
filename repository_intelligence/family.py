"""
LLMorch Repository Family Abstraction
Provides extensible, non-branching repository family adapters supporting
OpenTitan-style and Caliptra-style hardware security architectures.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from pydantic import BaseModel, Field
import os
import re

from schemas.analysis_unit import AnalysisUnit, AnalysisUnitType, PriorityLevel
from schemas.security_surface import (
    SecuritySurface,
    SecurityAsset,
    Countermeasure,
    TrustBoundary,
    EntryPoint,
    AttackerCapability,
)
from schemas.repository_intelligence import HW_SW_Contract


class RepositoryFamilyType(str, Enum):
    """Supported hardware/software security repository architectural archetypes."""
    OPEN_TITAN_STYLE = "OPEN_TITAN_STYLE"
    CALIPTRA_STYLE = "CALIPTRA_STYLE"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNKNOWN = "UNKNOWN"


class FamilyDetectionResult(BaseModel):
    """Detection confidence and evidence artifact for repository family classification."""
    family: RepositoryFamilyType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)
    detected_capabilities: List[str] = Field(default_factory=list)


class RepositoryFamilyAdapter(ABC):
    """
    Abstract Base Class for repository family architectures.
    Normalizes heterogeneous build flows, register formats, and HW/SW boundaries
    into uniform repository intelligence structures for LLMorch core.
    """

    @abstractmethod
    def detect(self, repo_root: Path) -> FamilyDetectionResult:
        """Inspects repository root and returns classification with evidence."""
        pass

    @abstractmethod
    def discover_layout(self, repo_root: Path) -> Dict[str, Any]:
        """Discovers primary directory layout (rtl, sw, registers, tests)."""
        pass

    @abstractmethod
    def discover_build_system(self, repo_root: Path) -> List[str]:
        """Identifies build system tools (Bazel, Meson, FuseSoC, Cargo xtask)."""
        pass

    @abstractmethod
    def discover_metadata(self, repo_root: Path) -> List[Dict[str, Any]]:
        """Extracts architectural metadata (HJSON, SystemRDL, .core)."""
        pass

    @abstractmethod
    def discover_components(self, repo_root: Path) -> List[str]:
        """Discovers functional hardware/software component modules."""
        pass

    @abstractmethod
    def discover_registers(self, repo_root: Path) -> List[Dict[str, Any]]:
        """Discovers memory-mapped registers, offsets, and access permissions."""
        pass

    @abstractmethod
    def discover_firmware(self, repo_root: Path) -> List[Dict[str, Any]]:
        """Discovers firmware/driver modules (DIF, ROM, Rust crates)."""
        pass

    @abstractmethod
    def discover_rtl(self, repo_root: Path) -> List[Dict[str, Any]]:
        """Discovers RTL modules and top-level integration files."""
        pass

    @abstractmethod
    def discover_hw_sw_contracts(self, repo_root: Path) -> List[HW_SW_Contract]:
        """Extracts binding between register metadata, firmware headers, and RTL."""
        pass

    @abstractmethod
    def build_security_surface(self, repo_root: Path) -> SecuritySurface:
        """Constructs security surface (trust boundaries, entry points, assets)."""
        pass

    @abstractmethod
    def construct_analysis_units(self, repo_root: Path) -> List[AnalysisUnit]:
        """Builds non-trivial security analysis units."""
        pass

    @abstractmethod
    def discover_validation_backends(self, repo_root: Path) -> List[str]:
        """Discovers verification tooling supported in this repo (Verilator, Cocotb, Formal)."""
        pass


class OpenTitanFamilyAdapter(RepositoryFamilyAdapter):
    """
    Adapter for OpenTitan-style silicon RoT repositories:
    Characterized by: FuseSoC .core files, HJSON register definitions,
    Bazel/Meson build flows, C DIFs (Device Interface Functions), SystemVerilog RTL.
    """

    def detect(self, repo_root: Path) -> FamilyDetectionResult:
        evidence = []
        capabilities = []
        confidence = 0.0

        core_files = list(repo_root.glob("**/*.core"))
        if core_files:
            evidence.append(f"Found {len(core_files)} FuseSoC .core file(s)")
            capabilities.append("fusesoc")
            confidence += 0.35

        hjson_files = list(repo_root.glob("**/*.hjson"))
        if hjson_files:
            evidence.append(f"Found {len(hjson_files)} HJSON register metadata file(s)")
            capabilities.append("hjson_registers")
            confidence += 0.35

        bazel_files = list(repo_root.glob("**/BUILD")) + list(repo_root.glob("**/BUILD.bazel"))
        if bazel_files:
            evidence.append(f"Found {len(bazel_files)} Bazel BUILD file(s)")
            capabilities.append("bazel_build")
            confidence += 0.2

        dif_files = list(repo_root.glob("**/dif_*.h")) + list(repo_root.glob("**/dif_*.c"))
        if dif_files:
            evidence.append(f"Found {len(dif_files)} C Device Interface Function (DIF) driver file(s)")
            capabilities.append("c_dif_drivers")
            confidence += 0.2

        if confidence >= 0.5:
            family = RepositoryFamilyType.OPEN_TITAN_STYLE
        elif confidence >= 0.2:
            family = RepositoryFamilyType.PARTIALLY_SUPPORTED
        else:
            family = RepositoryFamilyType.UNKNOWN

        return FamilyDetectionResult(
            family=family,
            confidence=min(confidence, 1.0),
            evidence=evidence,
            detected_capabilities=capabilities
        )

    def discover_layout(self, repo_root: Path) -> Dict[str, Any]:
        return {
            "rtl": str(repo_root / "hw"),
            "sw": str(repo_root / "sw"),
            "registers": str(repo_root / "hw" / "ip"),
            "tests": str(repo_root / "hw" / "dv")
        }

    def discover_build_system(self, repo_root: Path) -> List[str]:
        tools = []
        if list(repo_root.glob("**/BUILD*")):
            tools.append("bazel")
        if list(repo_root.glob("**/meson.build")):
            tools.append("meson")
        if list(repo_root.glob("**/*.core")):
            tools.append("fusesoc")
        return tools

    def discover_metadata(self, repo_root: Path) -> List[Dict[str, Any]]:
        meta = []
        for h in repo_root.glob("**/*.hjson"):
            meta.append({"path": str(h), "type": "HJSON_REGISTER_SPEC"})
        for c in repo_root.glob("**/*.core"):
            meta.append({"path": str(c), "type": "FUSESOC_CORE"})
        return meta

    def discover_components(self, repo_root: Path) -> List[str]:
        components = set()
        for p in repo_root.glob("hw/ip/*"):
            if p.is_dir():
                components.add(p.name)
        for p in repo_root.glob("sw/device/lib/dif/*"):
            if p.is_dir() or p.name.startswith("dif_"):
                components.add(p.stem.replace("dif_", ""))
        return sorted(list(components))

    def discover_registers(self, repo_root: Path) -> List[Dict[str, Any]]:
        regs = []
        for h in repo_root.glob("**/*.hjson"):
            regs.append({
                "source_file": str(h),
                "format": "HJSON",
                "component": h.stem.replace("_regs", "")
            })
        return regs

    def discover_firmware(self, repo_root: Path) -> List[Dict[str, Any]]:
        fw = []
        for d in repo_root.glob("sw/**/dif_*.c"):
            fw.append({"source_file": str(d), "type": "C_DIF_DRIVER"})
        return fw

    def discover_rtl(self, repo_root: Path) -> List[Dict[str, Any]]:
        rtl = []
        for sv in repo_root.glob("hw/**/*.sv"):
            rtl.append({"source_file": str(sv), "language": "SystemVerilog"})
        return rtl

    def discover_hw_sw_contracts(self, repo_root: Path) -> List[HW_SW_Contract]:
        contracts = []
        for h in repo_root.glob("**/*_regs.hjson"):
            comp = h.stem.replace("_regs", "")
            header = repo_root / f"sw/device/lib/dif/dif_{comp}.h"
            rtl = repo_root / f"hw/ip/{comp}/rtl/{comp}.sv"
            contracts.append(HW_SW_Contract(
                contract_id=f"contract-ot-{comp}",
                register_name=f"{comp}_regs",
                rtl_module=str(rtl) if rtl.exists() else None,
                hjson_ref=str(h),
                header_ref=str(header) if header.exists() else None,
                dif_ref=str(header) if header.exists() else None,
            ))
        return contracts

    def build_security_surface(self, repo_root: Path) -> SecuritySurface:
        return SecuritySurface(
            repository_id=repo_root.name,
            snapshot_id="snap-ot",
            assets=[SecurityAsset(name="Root Keys", asset_type="key", location="hw/ip/keymgr")],
            boundaries=[TrustBoundary(name="TL-UL Bus Boundary", from_domain="host", to_domain="device")],
            attacker_capabilities=[AttackerCapability.PHYSICAL, AttackerCapability.FIRMWARE],
            entry_points=[EntryPoint(name="MMIO Register Interface", interface_type="MMIO", location="hw/ip")]
        )

    def construct_analysis_units(self, repo_root: Path) -> List[AnalysisUnit]:
        units = []
        for comp in self.discover_components(repo_root):
            units.append(AnalysisUnit(
                repository_id=repo_root.name,
                snapshot_id="snap-ot",
                unit_type=AnalysisUnitType.HARDWARE_IP,
                domain="HARDWARE_SECURITY",
                name=f"ot_ip_{comp}",
                description=f"OpenTitan hardware IP module '{comp}' and associated DIF contract",
                priority=PriorityLevel.HIGH if comp in ["keymgr", "otp_ctrl", "aes", "rom_ctrl"] else PriorityLevel.MEDIUM
            ))
        return units

    def discover_validation_backends(self, repo_root: Path) -> List[str]:
        return ["Verilator", "SymbiYosys", "FuseSoC", "Bazel"]


class CaliptraFamilyAdapter(RepositoryFamilyAdapter):
    """
    Adapter for Caliptra-style silicon RoT repositories:
    Characterized by: Rust/Cargo xtask workflows, SystemRDL (*.rdl) register definitions,
    Rust firmware (ROM, Runtime, Drivers), Mailbox & SoC integration, Cocotb / Verilator / QEMU testbenches.
    """

    def detect(self, repo_root: Path) -> FamilyDetectionResult:
        evidence = []
        capabilities = []
        confidence = 0.0

        # 1. Cargo xtask detection
        xtask_dir = repo_root / "xtask"
        cargo_root = repo_root / "Cargo.toml"
        if cargo_root.exists() and xtask_dir.exists():
            evidence.append("Found Cargo workspace with xtask build flow")
            capabilities.append("cargo_xtask")
            confidence += 0.35
        elif cargo_root.exists():
            # Check for Caliptra crates inside Cargo.toml
            content = cargo_root.read_text(errors="ignore")
            if "caliptra" in content.lower():
                evidence.append("Found Caliptra Rust crate references in Cargo.toml")
                capabilities.append("caliptra_crates")
                confidence += 0.3

        # 2. SystemRDL register definitions
        rdl_files = list(repo_root.glob("**/*.rdl"))
        if rdl_files:
            evidence.append(f"Found {len(rdl_files)} SystemRDL (*.rdl) register metadata file(s)")
            capabilities.append("systemrdl_registers")
            confidence += 0.35

        # 3. Caliptra Mailbox / SoC registers
        mailbox_files = list(repo_root.glob("**/caliptra_top.sv")) + list(repo_root.glob("**/mbox*.sv"))
        if mailbox_files:
            evidence.append(f"Found Caliptra top-level or mailbox RTL module(s)")
            capabilities.append("caliptra_mailbox_rtl")
            confidence += 0.25

        # 4. Caliptra ROM/Firmware Rust packages
        rust_fw = list(repo_root.glob("**/rom/**/*.rs")) + list(repo_root.glob("**/runtime/**/*.rs"))
        if rust_fw:
            evidence.append(f"Found Caliptra Rust ROM/Runtime firmware source files")
            capabilities.append("rust_firmware")
            confidence += 0.2

        if confidence >= 0.5:
            family = RepositoryFamilyType.CALIPTRA_STYLE
        elif confidence >= 0.2:
            family = RepositoryFamilyType.PARTIALLY_SUPPORTED
        else:
            family = RepositoryFamilyType.UNKNOWN

        return FamilyDetectionResult(
            family=family,
            confidence=min(confidence, 1.0),
            evidence=evidence,
            detected_capabilities=capabilities
        )

    def discover_layout(self, repo_root: Path) -> Dict[str, Any]:
        return {
            "rtl": str(repo_root / "src"),
            "sw": str(repo_root / "sw"),
            "registers": str(repo_root / "registers"),
            "firmware": str(repo_root / "rom"),
            "tests": str(repo_root / "hw-model")
        }

    def discover_build_system(self, repo_root: Path) -> List[str]:
        tools = []
        if (repo_root / "Cargo.toml").exists():
            tools.append("cargo")
        if (repo_root / "xtask").exists():
            tools.append("cargo_xtask")
        if list(repo_root.glob("**/*.rdl")):
            tools.append("systemrdl_compiler")
        return tools

    def discover_metadata(self, repo_root: Path) -> List[Dict[str, Any]]:
        meta = []
        for rdl in repo_root.glob("**/*.rdl"):
            meta.append({"path": str(rdl), "type": "SYSTEMRDL_REGISTER_SPEC"})
        for cargo in repo_root.glob("**/Cargo.toml"):
            meta.append({"path": str(cargo), "type": "CARGO_MANIFEST"})
        return meta

    def discover_components(self, repo_root: Path) -> List[str]:
        components = set()
        for rdl in repo_root.glob("**/*.rdl"):
            components.add(rdl.stem)
        for cargo in repo_root.glob("**/Cargo.toml"):
            if cargo.parent != repo_root:
                components.add(cargo.parent.name)
        return sorted(list(components))

    def discover_registers(self, repo_root: Path) -> List[Dict[str, Any]]:
        regs = []
        for rdl in repo_root.glob("**/*.rdl"):
            regs.append({
                "source_file": str(rdl),
                "format": "SystemRDL",
                "component": rdl.stem
            })
        return regs

    def discover_firmware(self, repo_root: Path) -> List[Dict[str, Any]]:
        fw = []
        for rs in repo_root.glob("**/*.rs"):
            if any(part in rs.parts for part in ["rom", "runtime", "drivers"]):
                fw.append({"source_file": str(rs), "type": "RUST_FIRMWARE_MODULE"})
        return fw

    def discover_rtl(self, repo_root: Path) -> List[Dict[str, Any]]:
        rtl = []
        for sv in repo_root.glob("**/*.sv"):
            rtl.append({"source_file": str(sv), "language": "SystemVerilog"})
        return rtl

    def discover_hw_sw_contracts(self, repo_root: Path) -> List[HW_SW_Contract]:
        contracts = []
        for rdl in repo_root.glob("**/*.rdl"):
            comp = rdl.stem
            rs_driver = repo_root / f"drivers/src/{comp}.rs"
            rtl_module = repo_root / f"src/{comp}.sv"
            contracts.append(HW_SW_Contract(
                contract_id=f"contract-caliptra-{comp}",
                register_name=f"{comp}_regs",
                rtl_module=str(rtl_module) if rtl_module.exists() else None,
                hjson_ref=str(rdl),
                header_ref=str(rs_driver) if rs_driver.exists() else None,
                dif_ref=str(rs_driver) if rs_driver.exists() else None,
            ))
        return contracts

    def build_security_surface(self, repo_root: Path) -> SecuritySurface:
        return SecuritySurface(
            repository_id=repo_root.name,
            snapshot_id="snap-caliptra",
            assets=[
                SecurityAsset(name="Device Identity Keys (UDS/CDI)", asset_type="key", location="registers/fuse"),
                SecurityAsset(name="PCR Measurement Registers", asset_type="control_register", location="registers/pcr")
            ],
            boundaries=[
                TrustBoundary(name="SoC-Caliptra Mailbox Boundary", from_domain="SoC", to_domain="Caliptra"),
                TrustBoundary(name="Caliptra Internal Fuse Vault Boundary", from_domain="Caliptra_uC", to_domain="Fuse_Vault")
            ],
            attacker_capabilities=[
                AttackerCapability.FIRMWARE,
                AttackerCapability.PHYSICAL
            ],
            entry_points=[
                EntryPoint(name="Mailbox Command Registers", interface_type="MMIO", location="registers/mailbox.rdl"),
                EntryPoint(name="JTAG Debug Unlock Port", interface_type="bus_interface", location="src/jtag.sv")
            ]
        )

    def construct_analysis_units(self, repo_root: Path) -> List[AnalysisUnit]:
        units = []
        for comp in self.discover_components(repo_root):
            is_critical = comp in ["mailbox", "sha512", "key_vault", "doe", "pcr_bank"]
            units.append(AnalysisUnit(
                repository_id=repo_root.name,
                snapshot_id="snap-caliptra",
                unit_type=AnalysisUnitType.HARDWARE_IP,
                domain="HARDWARE_SECURITY",
                name=f"caliptra_{comp}",
                description=f"Caliptra hardware/firmware subsystem '{comp}'",
                priority=PriorityLevel.CRITICAL if is_critical else PriorityLevel.MEDIUM
            ))
        return units

    def discover_validation_backends(self, repo_root: Path) -> List[str]:
        return ["Cargo_xtask", "Verilator", "Cocotb", "Emulator"]


class GenericFallbackAdapter(RepositoryFamilyAdapter):
    """Fallback adapter for generic multi-language repositories."""

    def detect(self, repo_root: Path) -> FamilyDetectionResult:
        return FamilyDetectionResult(
            family=RepositoryFamilyType.UNKNOWN,
            confidence=0.1,
            evidence=["Generic repository fallback"],
            detected_capabilities=["generic_files"]
        )

    def discover_layout(self, repo_root: Path) -> Dict[str, Any]:
        return {"root": str(repo_root)}

    def discover_build_system(self, repo_root: Path) -> List[str]:
        return []

    def discover_metadata(self, repo_root: Path) -> List[Dict[str, Any]]:
        return []

    def discover_components(self, repo_root: Path) -> List[str]:
        return [p.name for p in repo_root.iterdir() if p.is_dir() and not p.name.startswith(".")]

    def discover_registers(self, repo_root: Path) -> List[Dict[str, Any]]:
        return []

    def discover_firmware(self, repo_root: Path) -> List[Dict[str, Any]]:
        return []

    def discover_rtl(self, repo_root: Path) -> List[Dict[str, Any]]:
        return []

    def discover_hw_sw_contracts(self, repo_root: Path) -> List[HW_SW_Contract]:
        return []

    def build_security_surface(self, repo_root: Path) -> SecuritySurface:
        return SecuritySurface(repository_id=repo_root.name, snapshot_id="snap-generic")

    def construct_analysis_units(self, repo_root: Path) -> List[AnalysisUnit]:
        return []

    def discover_validation_backends(self, repo_root: Path) -> List[str]:
        return ["Python_pytest"]


def detect_repository_family(repo_root: Path) -> Tuple[RepositoryFamilyType, RepositoryFamilyAdapter]:
    """
    Evaluates available family adapters against the repository root.
    Returns (detected_family, matching_adapter) without scattered if/else branching.
    """
    adapters = [
        OpenTitanFamilyAdapter(),
        CaliptraFamilyAdapter()
    ]

    best_match: Optional[Tuple[FamilyDetectionResult, RepositoryFamilyAdapter]] = None

    for adapter in adapters:
        detection = adapter.detect(repo_root)
        if best_match is None or detection.confidence > best_match[0].confidence:
            best_match = (detection, adapter)

    if best_match and best_match[0].confidence >= 0.3:
        return best_match[0].family, best_match[1]

    return RepositoryFamilyType.UNKNOWN, GenericFallbackAdapter()
