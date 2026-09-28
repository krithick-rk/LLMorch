"""
LLMorch Specification Ingestion Engine
Deterministically extracts requirements, claims, assumptions, register definitions,
interfaces, power/clock/reset specifications, and security claims from RM/TRM,
Markdown, text, SVD, and header specification artifacts.
"""

from __future__ import annotations

import re
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from schemas.soc_verification import Specification, Requirement
from schemas.soc_ontology import SoCBucket


class SpecificationIngestor:
    """
    Ingests technical reference manuals (TRM), register manuals (RM), and spec files.
    Performs deterministic parsing to identify requirements and security claims.
    """

    @staticmethod
    def ingest_file(file_path: str, document_title: Optional[str] = None) -> Dict[str, Any]:
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Specification file not found: {file_path}")

        title = document_title or path.stem.replace("_", " ").title()
        ext = path.suffix.lower()
        
        # Read text content
        raw_text = ""
        try:
            raw_text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            raw_text = path.read_text(encoding="latin-1", errors="replace")

        content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        # Document type detection
        doc_type = "TEXT"
        if ext in (".md", ".markdown"):
            doc_type = "MARKDOWN"
        elif ext == ".pdf":
            doc_type = "PDF"
        elif ext == ".svd":
            doc_type = "SVD"
        elif ext in (".h", ".hpp"):
            doc_type = "HEADER"
        elif ext in (".hjson", ".json", ".yaml", ".yml"):
            doc_type = "REGISTER_SPEC"

        sections = SpecificationIngestor._split_sections(raw_text, doc_type)
        requirements: List[Requirement] = []
        claims: List[str] = []
        assumptions: List[str] = []

        spec = Specification(
            title=title,
            document_type=doc_type,
            file_path=str(path),
            sections_count=len(sections),
            content_hash=content_hash
        )

        for sec_name, sec_text in sections.items():
            for line in sec_text.splitlines():
                l_str = line.strip()
                if not l_str:
                    continue
                # Match explicit Requirement: or REQ: or normative statements
                is_explicit_req = bool(re.match(r"^(?:[-*#0-9.]*\s*)?(?:Requirement|Req|SEC|HW|SW|VERIF)[\s\d_:-]", l_str, re.IGNORECASE))
                has_normative = any(w in l_str.lower() for w in (" must ", " shall ", " must not ", " shall not ", " is required to "))
                if is_explicit_req or (has_normative and len(l_str) > 20):
                    clean_req = re.sub(r"^(?:[-*#0-9.]*\s*)?(?:Requirement\s*\d*:\s*|Req\s*\d*:\s*)", "", l_str, flags=re.IGNORECASE).strip()
                    bucket = SpecificationIngestor._classify_bucket(clean_req)
                    is_sec = any(w in clean_req.lower() for w in ("security", "privilege", "auth", "lock", "secret", "key", "trust", "crypto", "tamper", "reset"))
                    req = Requirement(
                        spec_id=spec.spec_id,
                        section=sec_name,
                        title=f"{sec_name}: {clean_req[:60]}...",
                        description=clean_req,
                        primary_bucket=bucket,
                        is_security_critical=is_sec,
                        provenance=f"{path.name}#{sec_name}"
                    )
                    requirements.append(req)
                elif any(kw in l_str.lower() for kw in ("assume", "assumption", "precondition", "provided that")):
                    assumptions.append(l_str)
                elif any(kw in l_str.lower() for kw in ("guarantee", "claim", "ensures", "invariance")):
                    claims.append(l_str)

        spec.requirements_extracted = len(requirements)
        spec.extracted_claims = claims[:50]
        spec.assumptions = assumptions[:50]

        return {
            "specification": spec,
            "requirements": requirements,
            "claims": claims,
            "assumptions": assumptions
        }

    @staticmethod
    def _split_sections(text: str, doc_type: str) -> Dict[str, str]:
        sections: Dict[str, str] = {}
        current_section = "Overview"
        current_lines: List[str] = []

        header_re = re.compile(r"^(?:#{1,4}\s+|[0-9]+(?:\.[0-9]+)*\s+)([^\n]+)", re.MULTILINE)

        for line in text.splitlines():
            m = header_re.match(line)
            if m:
                if current_lines:
                    sections[current_section] = "\n".join(current_lines)
                    current_lines = []
                current_section = m.group(1).strip()
            else:
                current_lines.append(line)

        if current_lines:
            sections[current_section] = "\n".join(current_lines)

        return sections if sections else {"Full Document": text}

    @staticmethod
    def _classify_bucket(text: str) -> SoCBucket:
        t = text.lower()
        if any(w in t for w in ("clock", "pll", "oscillator", "clk")):
            return SoCBucket.CLOCKS
        elif any(w in t for w in ("reset", "rst", "por", "power-on")):
            return SoCBucket.RESETS
        elif any(w in t for w in ("cdc", "clock domain crossing", "synchronizer")):
            return SoCBucket.CDC
        elif any(w in t for w in ("rdc", "reset domain crossing")):
            return SoCBucket.RDC
        elif any(w in t for w in ("boot", "rom", "secure boot")):
            return SoCBucket.BOOT
        elif any(w in t for w in ("debug", "jtag", "dap", "trace")):
            return SoCBucket.DEBUG
        elif any(w in t for w in ("otp", "fuse", "lifecycle")):
            return SoCBucket.FUSES_OTP
        elif any(w in t for w in ("interrupt", "irq", "dma")):
            return SoCBucket.CROSS_IP_FLOWS
        elif any(w in t for w in ("memory", "sram", "dram", "mmu", "cache")):
            return SoCBucket.MEMORY_SYSTEM
        elif any(w in t for w in ("bus", "interconnect", "axi", "ahb", "tlul", "tilelink")):
            return SoCBucket.INTERCONNECT
        elif any(w in t for w in ("power", "sleep", "wake", "retention")):
            return SoCBucket.POWER_MODES
        elif any(w in t for w in ("pin", "pad", "mux", "gpio")):
            return SoCBucket.PIN_MUXING
        elif any(w in t for w in ("ecc", "parity", "safety", "fault")):
            return SoCBucket.ERROR_SAFETY
        return SoCBucket.SECURITY
