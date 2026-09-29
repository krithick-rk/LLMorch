"""
Repository Complexity Classification & Domain Evidence Extraction.
Section 15, 16, 17, 18, 19, 20, 21, 26, 27 of LLMorch Architecture.

Determines deterministic repository complexity tiers:
  MICRO, SMALL, MEDIUM, LARGE, SOC_SCALE
and scans evidence to drive 23-bucket applicability with explainable reasons.
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from schemas.soc_ontology import SoCBucket, BucketApplicability


class ComplexityTier(str, Enum):
    MICRO = "MICRO"          # 1–3 files, < 60 KB, simple single component
    SMALL = "SMALL"          # 4–12 files, < 300 KB, few modules
    MEDIUM = "MEDIUM"        # 13–40 files, < 2 MB, moderate subsystem
    LARGE = "LARGE"          # 41–150 files, multi-subsystem
    SOC_SCALE = "SOC_SCALE"  # > 150 files, full SoC hierarchy


class IntentDepth(str, Enum):
    QUICK = "QUICK"
    STANDARD = "STANDARD"
    DEEP = "DEEP"
    FULL_SOC = "FULL_SOC"


class DomainEvidence(BaseModel):
    has_resets: bool = False
    reset_signals: List[str] = Field(default_factory=list)
    has_clocks: bool = False
    clock_signals: List[str] = Field(default_factory=list)
    multi_clock: bool = False
    has_security_signals: bool = False
    security_keywords: List[str] = Field(default_factory=list)
    has_interconnect: bool = False
    interconnect_types: List[str] = Field(default_factory=list)
    has_csrs: bool = False
    has_debug: bool = False
    has_boot: bool = False
    has_fuses: bool = False
    has_power_modes: bool = False
    has_variants: bool = False
    has_gate_netlist: bool = False
    module_count: int = 0
    modules: List[str] = Field(default_factory=list)


def parse_intent_depth(intent: Optional[str], tier: ComplexityTier) -> IntentDepth:
    """Parses user intent string into explicit execution depth."""
    if not intent:
        return IntentDepth.QUICK if tier in (ComplexityTier.MICRO, ComplexityTier.SMALL) else IntentDepth.STANDARD

    lower = intent.lower()
    if any(k in lower for k in ("full soc", "complete soc", "all 23", "23-bucket", "full verification plan", "comprehensive soc")):
        return IntentDepth.FULL_SOC
    if any(k in lower for k in ("deep", "full security", "exhaustive", "formal signoff")):
        return IntentDepth.DEEP
    if any(k in lower for k in ("quick", "lint", "fast", "scan", "lightweight")):
        return IntentDepth.QUICK
    if any(k in lower for k in ("debug", "run", "analyze this repository", "analyze", "check")):
        return IntentDepth.QUICK if tier == ComplexityTier.MICRO else IntentDepth.STANDARD

    return IntentDepth.STANDARD


def classify_complexity(
    repo_path: str,
    analyzable_files_count: int,
    total_bytes: int,
    rtl_detected: bool,
    software_detected: bool,
    build_system_detected: bool
) -> Tuple[ComplexityTier, DomainEvidence]:
    """
    Deterministically classifies repository complexity using multiple architectural signals.
    """
    path = Path(repo_path).resolve()
    evidence = DomainEvidence()

    if not path.exists() or not path.is_dir():
        return ComplexityTier.MICRO, evidence

    # Scan analyzable files for domain evidence
    clocks: Set[str] = set()
    resets: Set[str] = set()
    sec_terms: Set[str] = set()
    modules: Set[str] = set()
    interconnects: Set[str] = set()

    file_count = 0
    for f in path.rglob("*"):
        if f.is_file() and not any(part.startswith(".") for part in f.parts):
            file_count += 1
            if f.suffix in (".v", ".sv", ".c", ".h", ".cpp", ".py"):
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")[:50000]
                except Exception:
                    continue

                # Clock signals
                for m in re.findall(r"\b(clk[a-zA-Z0-9_]*|clock[a-zA-Z0-9_]*)\b", content, re.IGNORECASE):
                    if len(m) <= 20:
                        clocks.add(m.lower())

                # Reset signals
                for m in re.findall(r"\b(rst[a-zA-Z0-9_]*|reset[a-zA-Z0-9_]*)\b", content, re.IGNORECASE):
                    if len(m) <= 20:
                        resets.add(m.lower())

                # Verilog modules
                for m in re.findall(r"\bmodule\s+([a-zA-Z0-9_]+)", content):
                    modules.add(m)

                # Security keywords
                for kw in ("crypto", "aes", "sha", "key", "secret", "pmp", "firewall", "privilege", "auth"):
                    if re.search(r"\b" + kw + r"\b", content, re.IGNORECASE):
                        sec_terms.add(kw)

                # Interconnect protocols
                for ic in ("axi", "ahb", "tlul", "tilelink", "wishbone", "apb"):
                    if re.search(r"\b" + ic + r"\b", content, re.IGNORECASE):
                        interconnects.add(ic.upper())

                # Debug
                if re.search(r"\b(jtag|dap|debug_req|dm_)\b", content, re.IGNORECASE):
                    evidence.has_debug = True

                # Boot
                if re.search(r"\b(bootrom|boot_mode|rom_exec)\b", content, re.IGNORECASE):
                    evidence.has_boot = True

                # Fuses / OTP
                if re.search(r"\b(otp|efuse|e_fuse)\b", content, re.IGNORECASE):
                    evidence.has_fuses = True

                # Power modes
                if re.search(r"\b(sleep_req|low_power|power_gate)\b", content, re.IGNORECASE):
                    evidence.has_power_modes = True

                # Product variants
                if re.search(r"\b(`ifdef|`ifndef)\b", content):
                    evidence.has_variants = True

                # CSRs
                if re.search(r"\b(reg_we|reg_re|csr_|addr_i)\b", content, re.IGNORECASE):
                    evidence.has_csrs = True

    evidence.has_clocks = len(clocks) > 0
    evidence.clock_signals = sorted(list(clocks))[:5]
    evidence.multi_clock = len(clocks) > 1

    evidence.has_resets = len(resets) > 0
    evidence.reset_signals = sorted(list(resets))[:5]

    evidence.has_security_signals = len(sec_terms) > 0
    evidence.security_keywords = sorted(list(sec_terms))[:5]

    evidence.has_interconnect = len(interconnects) > 0
    evidence.interconnect_types = sorted(list(interconnects))

    evidence.modules = sorted(list(modules))[:10]
    evidence.module_count = len(modules)

    # Deterministic complexity tier assignment
    effective_files = max(analyzable_files_count, file_count)
    if effective_files <= 3 and total_bytes < 80000 and evidence.module_count <= 2:
        tier = ComplexityTier.MICRO
    elif effective_files <= 12 and total_bytes < 350000 and evidence.module_count <= 5:
        tier = ComplexityTier.SMALL
    elif effective_files <= 40 and total_bytes < 2500000:
        tier = ComplexityTier.MEDIUM
    elif effective_files <= 150:
        tier = ComplexityTier.LARGE
    else:
        tier = ComplexityTier.SOC_SCALE

    return tier, evidence


def evaluate_bucket_evidence(
    bucket: SoCBucket,
    tier: ComplexityTier,
    intent: IntentDepth,
    evidence: DomainEvidence,
    rtl_detected: bool,
    software_detected: bool
) -> Tuple[BucketApplicability, str]:
    """
    Evaluates applicability of an SoC taxonomy bucket with explicit evidence-based rationale.
    """
    # If user explicitly requested FULL_SOC, permit all relevant buckets with explanation
    if intent == IntentDepth.FULL_SOC:
        return BucketApplicability.APPLICABLE, f"Included via full SoC verification taxonomy requested by operator."

    # For MICRO and SMALL repositories without full escalation:
    # Most specialized buckets are NOT_APPLICABLE
    if bucket == SoCBucket.RESETS:
        if evidence.has_resets:
            sigs = ", ".join(evidence.reset_signals[:3])
            return BucketApplicability.APPLICABLE, f"Reset signals detected ({sigs}) with reset controller logic."
        return BucketApplicability.NOT_APPLICABLE, "No dedicated reset controller or reset crossings detected."

    if bucket == SoCBucket.CLOCKS:
        if evidence.has_clocks:
            sigs = ", ".join(evidence.clock_signals[:3])
            return BucketApplicability.APPLICABLE, f"Clock distribution signals detected ({sigs})."
        return BucketApplicability.NOT_APPLICABLE, "No clock generation or PLL signals detected."

    if bucket in (SoCBucket.CDC, SoCBucket.RDC):
        if evidence.multi_clock:
            return BucketApplicability.APPLICABLE, f"Multiple clock domains detected ({', '.join(evidence.clock_signals[:3])})."
        return BucketApplicability.NOT_APPLICABLE, "Single clock/reset domain; cross-domain crossing not applicable."

    if bucket == SoCBucket.SECURITY:
        if evidence.has_security_signals or intent in (IntentDepth.DEEP, IntentDepth.STANDARD):
            terms = ", ".join(evidence.security_keywords) if evidence.security_keywords else "standard security baseline"
            return BucketApplicability.APPLICABLE, f"Security verification applicable ({terms})."
        return BucketApplicability.NOT_APPLICABLE, "No cryptographic or security privilege gates detected."

    if bucket == SoCBucket.IP_BOUNDARY:
        if rtl_detected:
            return BucketApplicability.APPLICABLE, f"RTL interface ports and pin boundaries present ({evidence.module_count} modules)."
        return BucketApplicability.NOT_APPLICABLE, "No hardware RTL boundaries found."

    if bucket == SoCBucket.CONNECTIVITY:
        if evidence.has_interconnect or evidence.module_count > 1:
            return BucketApplicability.APPLICABLE, f"Inter-module connectivity verified across {evidence.module_count} modules."
        return BucketApplicability.NOT_APPLICABLE, "Single module; no inter-module interconnect detected."

    if bucket == SoCBucket.INTERCONNECT:
        if evidence.has_interconnect:
            return BucketApplicability.APPLICABLE, f"Bus interconnect detected ({', '.join(evidence.interconnect_types)})."
        return BucketApplicability.NOT_APPLICABLE, "No bus interconnect fabric detected."

    if bucket == SoCBucket.DEBUG:
        if evidence.has_debug:
            return BucketApplicability.APPLICABLE, "Debug/JTAG hardware signals detected."
        return BucketApplicability.NOT_APPLICABLE, "No JTAG or debug port interfaces detected."

    if bucket == SoCBucket.BOOT:
        if evidence.has_boot:
            return BucketApplicability.APPLICABLE, "Bootrom / ROM sequence signals detected."
        return BucketApplicability.NOT_APPLICABLE, "No boot ROM or reset vector sequencer detected."

    if bucket == SoCBucket.FUSES_OTP:
        if evidence.has_fuses:
            return BucketApplicability.APPLICABLE, "OTP / eFuse registers detected."
        return BucketApplicability.NOT_APPLICABLE, "No OTP fuse or macro memory evidence detected."

    if bucket == SoCBucket.POWER_MODES:
        if evidence.has_power_modes:
            return BucketApplicability.APPLICABLE, "Power domain / sleep sequencing signals detected."
        return BucketApplicability.NOT_APPLICABLE, "Single power domain; low-power states not applicable."

    if bucket == SoCBucket.PRODUCT_VARIANTS:
        if evidence.has_variants and tier not in (ComplexityTier.MICRO, ComplexityTier.SMALL):
            return BucketApplicability.APPLICABLE, "Multi-configuration parameters or ifdef macros detected."
        return BucketApplicability.NOT_APPLICABLE, "No variant or configuration macros detected in repository."

    if bucket == SoCBucket.GATE_STATIC_SIGNOFF:
        if evidence.has_gate_netlist:
            return BucketApplicability.APPLICABLE, "Gate-level netlist present for static signoff."
        return BucketApplicability.NOT_APPLICABLE, "RTL source tree only; gate netlists not present."

    if bucket == SoCBucket.CLOSURE:
        return BucketApplicability.APPLICABLE, "Verification closure tracking for applicable plan objectives."

    # For MICRO repositories, all remaining buckets are NOT_APPLICABLE
    if tier == ComplexityTier.MICRO:
        return BucketApplicability.NOT_APPLICABLE, f"Not applicable for MICRO complexity repository (1–3 files)."

    if tier == ComplexityTier.SMALL:
        return BucketApplicability.NOT_APPLICABLE, f"Not applicable for SMALL complexity repository without explicit evidence."

    return BucketApplicability.UNKNOWN, "Applicability depends on further specification review."


def get_task_limit_for_tier(tier: ComplexityTier, intent: IntentDepth) -> int:
    """Hard task bounds (Section 19)."""
    if intent == IntentDepth.FULL_SOC:
        return 23
    if tier == ComplexityTier.MICRO:
        return 3
    if tier == ComplexityTier.SMALL:
        return 8
    if tier == ComplexityTier.MEDIUM:
        return 16
    return 23
