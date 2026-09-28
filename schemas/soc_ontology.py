"""
LLMorch 23-Bucket SoC Verification Ontology
Authoritative taxonomy and bucket definitions based on the LLMorch Architecture Transition Plan.
Extensible, versioned ontology covering IP, interconnect, clocks, resets, security, and closure.
"""

from enum import Enum
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class SoCBucket(str, Enum):
    IP_BOUNDARY = "ip_boundary"
    CONNECTIVITY = "connectivity"
    CROSS_IP_FLOWS = "cross_ip_flows"
    PERFORMANCE = "performance"
    BLAST_RADIUS = "blast_radius"
    POWER_MODES = "power_modes"
    CLOCKS = "clocks"
    RESETS = "resets"
    CDC = "cdc"
    RDC = "rdc"
    X_INIT = "x_init"
    PIN_MUXING = "pin_muxing"
    ERROR_SAFETY = "error_safety"
    SECURITY = "security"
    DEBUG = "debug"
    BOOT = "boot"
    MEMORY_SYSTEM = "memory_system"
    INTERCONNECT = "interconnect"
    PROCESSOR_INTEGRATION = "processor_integration"
    FUSES_OTP = "fuses_otp"
    PRODUCT_VARIANTS = "product_variants"
    GATE_STATIC_SIGNOFF = "gate_static_signoff"
    CLOSURE = "closure"


class BucketApplicability(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class BucketDefinition(BaseModel):
    bucket_number: int
    bucket: SoCBucket
    name: str
    scope_description: str
    recommended_role: str
    recommended_tools: List[str]
    category: str


SOC_BUCKET_DEFINITIONS: Dict[SoCBucket, BucketDefinition] = {
    SoCBucket.IP_BOUNDARY: BucketDefinition(
        bucket_number=1,
        bucket=SoCBucket.IP_BOUNDARY,
        name="IP Boundary",
        scope_description="Addressing, register access, privilege/security gates, reset/power boundary behavior",
        recommended_role="SoC Asset & Boundary",
        recommended_tools=["verilator", "yosys", "semgrep"],
        category="Architecture & Connectivity"
    ),
    SoCBucket.CONNECTIVITY: BucketDefinition(
        bucket_number=2,
        bucket=SoCBucket.CONNECTIVITY,
        name="Connectivity",
        scope_description="Bus, clocks, resets, IRQ, DMA, pins, sidebands, power/debug paths",
        recommended_role="Architecture / Connectivity",
        recommended_tools=["verilator", "yosys", "slang"],
        category="Architecture & Connectivity"
    ),
    SoCBucket.CROSS_IP_FLOWS: BucketDefinition(
        bucket_number=3,
        bucket=SoCBucket.CROSS_IP_FLOWS,
        name="Cross-IP Flows",
        scope_description="DMA/IRQ/trigger/wake-up, cross-subsystem data paths, multi-master scenarios",
        recommended_role="Architecture / Connectivity",
        recommended_tools=["cocotb", "verilator"],
        category="Architecture & Connectivity"
    ),
    SoCBucket.PERFORMANCE: BucketDefinition(
        bucket_number=4,
        bucket=SoCBucket.PERFORMANCE,
        name="Performance",
        scope_description="Bandwidth, latency, arbitration, QoS, DVFS contention",
        recommended_role="Power / Performance",
        recommended_tools=["cocotb"],
        category="Performance & Power"
    ),
    SoCBucket.BLAST_RADIUS: BucketDefinition(
        bucket_number=5,
        bucket=SoCBucket.BLAST_RADIUS,
        name="Blast Radius",
        scope_description="Reset, power, clock, watchdog, bus/ECC fault containment and isolation",
        recommended_role="Power / Performance",
        recommended_tools=["verilator", "yosys"],
        category="Performance & Power"
    ),
    SoCBucket.POWER_MODES: BucketDefinition(
        bucket_number=6,
        bucket=SoCBucket.POWER_MODES,
        name="Power Modes",
        scope_description="Entry/exit sequencing, wake-up, retention, isolation cells",
        recommended_role="Power / Performance",
        recommended_tools=["verilator", "slang"],
        category="Performance & Power"
    ),
    SoCBucket.CLOCKS: BucketDefinition(
        bucket_number=7,
        bucket=SoCBucket.CLOCKS,
        name="Clocks",
        scope_description="Trees, PLLs, muxes, dividers, clock gating, dynamic switching",
        recommended_role="CDC / RDC / Clock / Reset",
        recommended_tools=["verilator", "yosys"],
        category="Clock & Reset"
    ),
    SoCBucket.RESETS: BucketDefinition(
        bucket_number=8,
        bucket=SoCBucket.RESETS,
        name="Resets",
        scope_description="Reset sources, trees, sequencing, synchronization, reset status flags",
        recommended_role="CDC / RDC / Clock / Reset",
        recommended_tools=["verilator", "yosys"],
        category="Clock & Reset"
    ),
    SoCBucket.CDC: BucketDefinition(
        bucket_number=9,
        bucket=SoCBucket.CDC,
        name="CDC (Clock Domain Crossing)",
        scope_description="Crossings, synchronizers, async FIFOs, reconvergence",
        recommended_role="CDC / RDC / Clock / Reset",
        recommended_tools=["yosys", "verilator"],
        category="Clock & Reset"
    ),
    SoCBucket.RDC: BucketDefinition(
        bucket_number=10,
        bucket=SoCBucket.RDC,
        name="RDC (Reset Domain Crossing)",
        scope_description="Reset domain crossings, ordering, in-flight transactions during reset assertion",
        recommended_role="CDC / RDC / Clock / Reset",
        recommended_tools=["yosys", "verilator"],
        category="Clock & Reset"
    ),
    SoCBucket.X_INIT: BucketDefinition(
        bucket_number=11,
        bucket=SoCBucket.X_INIT,
        name="X-Init",
        scope_description="Undefined state propagation, memory/ECC initialization, reset state coverage",
        recommended_role="CDC / RDC / Clock / Reset",
        recommended_tools=["verilator", "yosys"],
        category="Clock & Reset"
    ),
    SoCBucket.PIN_MUXING: BucketDefinition(
        bucket_number=12,
        bucket=SoCBucket.PIN_MUXING,
        name="Pin Muxing",
        scope_description="Alternate functions, pad conflicts, reset defaults, debug/boot pin multiplexing",
        recommended_role="Architecture / Connectivity",
        recommended_tools=["verilator", "semgrep"],
        category="Architecture & Connectivity"
    ),
    SoCBucket.ERROR_SAFETY: BucketDefinition(
        bucket_number=13,
        bucket=SoCBucket.ERROR_SAFETY,
        name="Error / Safety",
        scope_description="ECC, watchdogs, fault escalation, lockstep, parity check paths",
        recommended_role="Threat Modeling",
        recommended_tools=["verilator", "cocotb"],
        category="Security & Lifecycle"
    ),
    SoCBucket.SECURITY: BucketDefinition(
        bucket_number=14,
        bucket=SoCBucket.SECURITY,
        name="Security",
        scope_description="Protection units, TrustZone/firewalls, security lifecycle, debug authorization",
        recommended_role="Vulnerability / Security Verification",
        recommended_tools=["yosys", "verilator", "z3", "semgrep"],
        category="Security & Lifecycle"
    ),
    SoCBucket.DEBUG: BucketDefinition(
        bucket_number=15,
        bucket=SoCBucket.DEBUG,
        name="Debug",
        scope_description="DAP access, core freeze, trace, multi-core debug, secure debug unlock",
        recommended_role="Boot / Debug / OTP / Lifecycle",
        recommended_tools=["verilator", "semgrep"],
        category="Security & Lifecycle"
    ),
    SoCBucket.BOOT: BucketDefinition(
        bucket_number=16,
        bucket=SoCBucket.BOOT,
        name="Boot",
        scope_description="Boot sources, ROM execution, secure boot verification, fallback paths, multi-core release",
        recommended_role="Boot / Debug / OTP / Lifecycle",
        recommended_tools=["verilator", "semgrep"],
        category="Security & Lifecycle"
    ),
    SoCBucket.MEMORY_SYSTEM: BucketDefinition(
        bucket_number=17,
        bucket=SoCBucket.MEMORY_SYSTEM,
        name="Memory / System",
        scope_description="Memory map, coherency, attributes, atomics, RM/RTL register consistency",
        recommended_role="Memory / Interconnect / Coherency",
        recommended_tools=["verilator", "slang", "semgrep"],
        category="Memory & Interconnect"
    ),
    SoCBucket.INTERCONNECT: BucketDefinition(
        bucket_number=18,
        bucket=SoCBucket.INTERCONNECT,
        name="Interconnect",
        scope_description="Bus reachability, transaction ordering, QoS, error responses, deadlock freedom",
        recommended_role="Memory / Interconnect / Coherency",
        recommended_tools=["verilator", "yosys"],
        category="Memory & Interconnect"
    ),
    SoCBucket.PROCESSOR_INTEGRATION: BucketDefinition(
        bucket_number=19,
        bucket=SoCBucket.PROCESSOR_INTEGRATION,
        name="Processor Integration",
        scope_description="CPU cores, caches/TCM, interrupt controllers, timer integration",
        recommended_role="Memory / Interconnect / Coherency",
        recommended_tools=["verilator", "cocotb"],
        category="Memory & Interconnect"
    ),
    SoCBucket.FUSES_OTP: BucketDefinition(
        bucket_number=20,
        bucket=SoCBucket.FUSES_OTP,
        name="Fuses / OTP",
        scope_description="OTP loading, shadow registers, ECC protection, feature enable/disable controls",
        recommended_role="Boot / Debug / OTP / Lifecycle",
        recommended_tools=["verilator", "semgrep"],
        category="Security & Lifecycle"
    ),
    SoCBucket.PRODUCT_VARIANTS: BucketDefinition(
        bucket_number=21,
        bucket=SoCBucket.PRODUCT_VARIANTS,
        name="Product Variants",
        scope_description="Memory size, package options, peripheral presence, device ID configuration",
        recommended_role="Verification Planning",
        recommended_tools=["semgrep", "slang"],
        category="Architecture & Connectivity"
    ),
    SoCBucket.GATE_STATIC_SIGNOFF: BucketDefinition(
        bucket_number=22,
        bucket=SoCBucket.GATE_STATIC_SIGNOFF,
        name="Gate / Static Sign-off",
        scope_description="Formal checks, linting, GLS/SDF, logical equivalence",
        recommended_role="Critic",
        recommended_tools=["yosys", "verilator", "z3", "boolector"],
        category="Sign-off & Closure"
    ),
    SoCBucket.CLOSURE: BucketDefinition(
        bucket_number=23,
        bucket=SoCBucket.CLOSURE,
        name="Closure",
        scope_description="Requirement-to-test traceability, coverage aggregation, regression, waivers, residual gaps",
        recommended_role="Closure",
        recommended_tools=["verilator", "cocotb"],
        category="Sign-off & Closure"
    ),
}


class BucketStatusRecord(BaseModel):
    bucket: SoCBucket
    name: str
    applicability: BucketApplicability
    rationale: str
    objectives_count: int = 0
    covered_objectives: int = 0
    gaps_count: int = 0
    coverage_percentage: float = 0.0
    recommended_role: str
    recommended_tools: List[str]
    category: str


def get_bucket_definition(bucket: SoCBucket) -> BucketDefinition:
    return SOC_BUCKET_DEFINITIONS[bucket]


def list_all_bucket_definitions() -> List[BucketDefinition]:
    return sorted(list(SOC_BUCKET_DEFINITIONS.values()), key=lambda x: x.bucket_number)


BUCKET_DEFINITIONS = SOC_BUCKET_DEFINITIONS


def get_bucket_for_concept(concept: str) -> SoCBucket:
    """Helper to map a keyword or concept to an SoC bucket."""
    c = concept.lower()
    if any(k in c for k in ["clk", "clock", "pll"]):
        return SoCBucket.CLOCKS
    if any(k in c for k in ["rst", "reset"]):
        return SoCBucket.RESETS
    if "cdc" in c:
        return SoCBucket.CDC
    if "rdc" in c:
        return SoCBucket.RDC
    if any(k in c for k in ["power", "pwr", "dvfs", "retention"]):
        return SoCBucket.POWER_MODES
    if any(k in c for k in ["dap", "jtag", "debug", "trace"]):
        return SoCBucket.DEBUG
    if any(k in c for k in ["boot", "rom", "otp", "fuse"]):
        return SoCBucket.BOOT
    if any(k in c for k in ["security", "sec", "firewall", "trustzone", "crypto", "aes"]):
        return SoCBucket.SECURITY
    if any(k in c for k in ["mem", "dram", "sram", "cache", "axi", "ahb", "tlul"]):
        return SoCBucket.MEMORY_SYSTEM
    if any(k in c for k in ["bus", "interconnect", "noc", "fabric"]):
        return SoCBucket.INTERCONNECT
    if any(k in c for k in ["waiver", "gap", "coverage", "closure", "signoff"]):
        return SoCBucket.CLOSURE
    return SoCBucket.IP_BOUNDARY
