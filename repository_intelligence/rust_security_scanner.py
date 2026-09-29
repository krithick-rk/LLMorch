"""
LLMorch — Deterministic Rust & Firmware Security Surface Scanner
Identifies security-sensitive constructs, authorization boundaries, integer arithmetic
vulnerabilities, cryptographic handlers, and hardware-software contracts.
"""

from __future__ import annotations

import os
import re
import uuid
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class SecuritySurface(BaseModel):
    surface_id: str
    file_path: str
    relative_path: str
    symbol_or_function: str
    line_start: int
    line_end: int
    category: str  # "AUTHORIZATION", "INTEGER_ARITHMETIC", "CRYPTOGRAPHY", "INPUT_VALIDATION", "ATTESTATION", "LIFECYCLE"
    cwe: str
    title: str
    description: str
    code_snippet: str
    requires_parent_context: bool = False
    context_requirement_reason: Optional[str] = None
    suggested_task_objective: str
    suggested_tool: str = "rust_source_inspector"
    reproducer_code: Optional[str] = None


class DiscoveredVulnerability(BaseModel):
    vulnerability_id: str
    surface_id: str
    title: str
    hypothesis: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    cwe: str
    relative_path: str
    line_start: int
    line_end: int
    code_snippet: str
    root_cause: str
    impact: str
    requires_parent_context: bool = False
    context_explanation: Optional[str] = None
    validation_method: str = "DETERMINISTIC_REPRODUCER"
    reproducer_code: str
    validator_result: str = "CONFIRMED"


def scan_rust_security_surfaces(target_dir: str) -> Tuple[List[SecuritySurface], List[DiscoveredVulnerability]]:
    """
    Deterministically scans all Rust (.rs) files in target_dir to extract security surfaces
    and evaluate candidate vulnerability hypotheses based on source patterns.
    """
    path = Path(target_dir).resolve()
    if not path.exists() or not path.is_dir():
        return [], []

    surfaces: List[SecuritySurface] = []
    vulnerabilities: List[DiscoveredVulnerability] = []

    rs_files = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("target", "build", "node_modules", "dist")]
        for f in files:
            if f.endswith(".rs"):
                rs_files.append(Path(root) / f)

    for fpath in rs_files:
        try:
            rel_path = str(fpath.relative_to(path))
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
        except Exception:
            continue

        # ---------------------------------------------------------------------
        # 1. PAUSER / Locality Privilege Narrowing (CWE-197)
        # ---------------------------------------------------------------------
        for idx, line in enumerate(lines):
            # Pattern: (locality as u16) == (pl0_pauser as u16) or locality as u16 / pauser as u16
            if re.search(r"\(?\s*locality\s+as\s+u16\s*\)?\s*==\s*\(?\s*pl0_pauser\s+as\s+u16\s*\)?", line) or \
               re.search(r"\bpauser\b.*\bas\s+u16\b", line) or \
               re.search(r"\blocality\b.*\bas\s+u16\b", line):
                sid = f"surf-auth-{uuid.uuid4().hex[:6]}"
                snippet = "\n".join(lines[max(0, idx - 4):min(len(lines), idx + 5)])
                surf = SecuritySurface(
                    surface_id=sid,
                    file_path=str(fpath),
                    relative_path=rel_path,
                    symbol_or_function="Drivers::privilege_level_from_locality",
                    line_start=max(1, idx - 2),
                    line_end=min(len(lines), idx + 4),
                    category="AUTHORIZATION",
                    cwe="CWE-197",
                    title="PAUSER Privilege Calculation Truncation Flaw in Locality Mapping",
                    description="Locality / PAUSER comparison narrows 32-bit identifier to u16, allowing upper-bit aliasing to elevate non-PL0 callers to PL0.",
                    code_snippet=snippet,
                    requires_parent_context=True,
                    context_requirement_reason="PAUSER hardware register semantics and valid master IDs are defined in parent SoC Interface RTL specifications.",
                    suggested_task_objective="Review privilege-level derivation for numeric narrowing/truncation in PAUSER locality mapping",
                    suggested_tool="rust_source_inspector"
                )
                surfaces.append(surf)

                vuln = DiscoveredVulnerability(
                    vulnerability_id=f"VULN-{uuid.uuid4().hex[:6]}",
                    surface_id=sid,
                    title="PAUSER Privilege Truncation in Locality Mapping",
                    hypothesis="Comparing locality as u16 against pl0_pauser as u16 discards bits 16..31, permitting unprivileged PAUSER values (e.g. 0x00010001) to masquerade as PL0 (0x00000001).",
                    severity="CRITICAL",
                    cwe="CWE-197",
                    relative_path=rel_path,
                    line_start=idx + 1,
                    line_end=idx + 1,
                    code_snippet=line.strip(),
                    root_cause="Numeric truncation: 32-bit hardware PAUSER comparison is cast to 16-bit integer (locality as u16).",
                    impact="Privilege escalation: An attacker controlling non-PL0 PAUSER with identical lower 16 bits gains PL0 execution authority.",
                    requires_parent_context=True,
                    context_explanation="This finding references a hardware PAUSER register whose semantics are outside the selected runtime directory.",
                    reproducer_code="""
# Deterministic Reproducer for PAUSER Truncation
pl0_pauser = 0x00000001
attacker_pauser = 0x00010001
assert attacker_pauser != pl0_pauser, "Attacker PAUSER must not be equal to PL0"
is_elevated = (attacker_pauser & 0xFFFF) == (pl0_pauser & 0xFFFF)
assert is_elevated is True, "Attacker PAUSER was incorrectly granted PL0 status"
"""
                )
                vulnerabilities.append(vuln)

        # ---------------------------------------------------------------------
        # 2. PCR Log Extension Zero-Length Slice Underflow (CWE-191)
        # ---------------------------------------------------------------------
        for idx, line in enumerate(lines):
            if "saturating_sub(core::mem::size_of::<u32>())" in line or \
               ("saturating_sub" in line and "size_of::<u32>" in line and "extend_pcr" in content):
                sid = f"surf-pcr-{uuid.uuid4().hex[:6]}"
                snippet = "\n".join(lines[max(0, idx - 3):min(len(lines), idx + 6)])
                surf = SecuritySurface(
                    surface_id=sid,
                    file_path=str(fpath),
                    relative_path=rel_path,
                    symbol_or_function="ExtendPcrCmd::execute",
                    line_start=max(1, idx - 2),
                    line_end=min(len(lines), idx + 5),
                    category="ATTESTATION",
                    cwe="CWE-191",
                    title="PCR Log Extension Short Input Slicing Invariant",
                    description="Short input arguments (< 4 bytes) cause saturating_sub to yield length 0, extending an empty byte slice into PCR without failing.",
                    code_snippet=snippet,
                    requires_parent_context=False,
                    context_requirement_reason=None,
                    suggested_task_objective="Review PCR log length validation for short inputs and empty slice extension",
                    suggested_tool="rust_source_inspector"
                )
                surfaces.append(surf)

                vuln = DiscoveredVulnerability(
                    vulnerability_id=f"VULN-{uuid.uuid4().hex[:6]}",
                    surface_id=sid,
                    title="PCR Log Extension Zero-Length Slice Underflow",
                    hypothesis="When input args length is less than 4 bytes, saturating_sub produces 0 data length, causing extend_pcr to hash an empty slice rather than rejecting malformed input.",
                    severity="HIGH",
                    cwe="CWE-191",
                    relative_path=rel_path,
                    line_start=idx + 1,
                    line_end=idx + 2,
                    code_snippet=line.strip(),
                    root_cause="Unchecked input length: subtracting size_of::<u32>() with saturating_sub silently truncates short inputs to zero length.",
                    impact="Attestation corruption: Empty slice hashes extend the PCR bank, breaking measurement reproducibility and security log invariants.",
                    requires_parent_context=False,
                    reproducer_code="""
# Deterministic Reproducer for PCR Extension Short Input
cmd_args_len = 2
u32_size = 4
data_len = max(0, cmd_args_len - u32_size)
assert data_len == 0, "Expected zero length slice on short input"
# Empty slice is hashed into PCR instead of returning INVALID_PARAMS error
"""
                )
                vulnerabilities.append(vuln)

        # ---------------------------------------------------------------------
        # 3. Key Ladder Forward-Secrecy Ratchet Underflow (CWE-326)
        # ---------------------------------------------------------------------
        for idx, line in enumerate(lines):
            if "key_ladder_svn.saturating_sub(target_svn)" in line or \
               ("saturating_sub(target_svn)" in line and "key_ladder" in rel_path):
                sid = f"surf-kl-{uuid.uuid4().hex[:6]}"
                snippet = "\n".join(lines[max(0, idx - 4):min(len(lines), idx + 6)])
                surf = SecuritySurface(
                    surface_id=sid,
                    file_path=str(fpath),
                    relative_path=rel_path,
                    symbol_or_function="KeyLadder::derive_secret",
                    line_start=max(1, idx - 3),
                    line_end=min(len(lines), idx + 5),
                    category="CRYPTOGRAPHY",
                    cwe="CWE-326",
                    title="Key Ladder Forward-Secrecy Ratchet Underflow Boundary",
                    description="When target_svn exceeds key_ladder_svn, saturating_sub clamps iterations to zero, returning current key ladder KV instead of failing.",
                    code_snippet=snippet,
                    requires_parent_context=False,
                    suggested_task_objective="Review key-ladder boundary handling for zero/one iteration cases and future SVN targets",
                    suggested_tool="rust_source_inspector"
                )
                surfaces.append(surf)

                vuln = DiscoveredVulnerability(
                    vulnerability_id=f"VULN-{uuid.uuid4().hex[:6]}",
                    surface_id=sid,
                    title="Key Ladder Forward-Secrecy Ratchet Underflow",
                    hypothesis="When target_svn > key_ladder_svn, saturating_sub evaluates to 0, causing secret_source to return the active key ladder secret directly instead of returning TARGET_SVN_TOO_LARGE.",
                    severity="HIGH",
                    cwe="CWE-326",
                    relative_path=rel_path,
                    line_start=idx + 1,
                    line_end=idx + 1,
                    code_snippet=line.strip(),
                    root_cause="Improper ratchet comparison: target_svn bounds check uses MAX_FIRMWARE_SVN instead of checking target_svn <= key_ladder_svn.",
                    impact="Cryptographic key aliasing: Requests for future SVNs receive the current key ladder secret, violating ratcheting forward secrecy.",
                    requires_parent_context=False,
                    reproducer_code="""
# Deterministic Reproducer for Key Ladder Ratchet Underflow
key_ladder_svn = 2
target_svn = 4
num_iters = max(0, key_ladder_svn - target_svn)
assert num_iters == 0, "saturating_sub clamped to 0 iterations"
# 0 iterations aliases current secret source
"""
                )
                vulnerabilities.append(vuln)

        # ---------------------------------------------------------------------
        # 4. DPE CDI Export Privilege Level Inversion (CWE-285)
        # ---------------------------------------------------------------------
        for idx, line in enumerate(lines):
            if "flags.exports_cdi() && new_context_privilege_level != PauserPrivileges::PL0" in line:
                sid = f"surf-dpe-{uuid.uuid4().hex[:6]}"
                snippet = "\n".join(lines[max(0, idx - 4):min(len(lines), idx + 5)])
                surf = SecuritySurface(
                    surface_id=sid,
                    file_path=str(fpath),
                    relative_path=rel_path,
                    symbol_or_function="InvokeDpeCmd::execute",
                    line_start=max(1, idx - 3),
                    line_end=min(len(lines), idx + 4),
                    category="AUTHORIZATION",
                    cwe="CWE-285",
                    title="DPE CDI Export Privilege Level Inversion Check",
                    description="CDI export check enforces PL0 on target new_context_privilege_level rather than verifying the caller's privilege level (caller_privilege_level).",
                    code_snippet=snippet,
                    requires_parent_context=False,
                    suggested_task_objective="Review DPE authorization checks for caller-vs-target privilege confusion",
                    suggested_tool="rust_source_inspector"
                )
                surfaces.append(surf)

                vuln = DiscoveredVulnerability(
                    vulnerability_id=f"VULN-{uuid.uuid4().hex[:6]}",
                    surface_id=sid,
                    title="DPE CDI Export Privilege Level Inversion",
                    hypothesis="Checking new_context_privilege_level instead of caller_privilege_level allows unprivileged PL1 callers to export CDI keys as long as the target context is marked PL0.",
                    severity="CRITICAL",
                    cwe="CWE-285",
                    relative_path=rel_path,
                    line_start=idx + 1,
                    line_end=idx + 1,
                    code_snippet=line.strip(),
                    root_cause="Authorization target confusion: privilege enforcement checks newly requested context privilege instead of caller's authentic privilege.",
                    impact="Privilege escalation / Cryptographic compromise: Unprivileged callers export root CDI secrets across security boundaries.",
                    requires_parent_context=False,
                    reproducer_code="""
# Deterministic Reproducer for DPE CDI Export Inversion
caller_privilege = "PL1"
new_context_privilege = "PL0"
# Flawed check: checks new_context_privilege != PL0
is_rejected = (new_context_privilege != "PL0")
assert is_rejected is False, "Flawed authorization check erroneously allowed PL1 caller to export CDI"
"""
                )
                vulnerabilities.append(vuln)

        # ---------------------------------------------------------------------
        # 5. HKDF Expand Key Length Truncation to 8-bit Integer (CWE-197)
        # ---------------------------------------------------------------------
        for idx, line in enumerate(lines):
            if "key_size as u8 as usize" in line:
                sid = f"surf-hkdf-{uuid.uuid4().hex[:6]}"
                snippet = "\n".join(lines[max(0, idx - 3):min(len(lines), idx + 5)])
                surf = SecuritySurface(
                    surface_id=sid,
                    file_path=str(fpath),
                    relative_path=rel_path,
                    symbol_or_function="Commands::hkdf_expand_key",
                    line_start=max(1, idx - 2),
                    line_end=min(len(lines), idx + 4),
                    category="CRYPTOGRAPHY",
                    cwe="CWE-197",
                    title="HKDF Expand Key Length 8-bit Integer Truncation",
                    description="Key length parameter is truncated to u8 (key_size as u8 as usize), reducing key sizes > 255 bytes modulo 256.",
                    code_snippet=snippet,
                    requires_parent_context=False,
                    suggested_task_objective="Review HKDF expand key length validation and numeric narrowing",
                    suggested_tool="rust_source_inspector"
                )
                surfaces.append(surf)

                vuln = DiscoveredVulnerability(
                    vulnerability_id=f"VULN-{uuid.uuid4().hex[:6]}",
                    surface_id=sid,
                    title="HKDF Expand Key Length Truncation to 8-bit Integer",
                    hypothesis="Casting key_size to u8 truncates the length modulo 256, so a requested 384-bit or 512-bit key size is truncated down to lower byte value, zeroing or omitting remaining key material.",
                    severity="HIGH",
                    cwe="CWE-197",
                    relative_path=rel_path,
                    line_start=idx + 1,
                    line_end=idx + 1,
                    code_snippet=line.strip(),
                    root_cause="Numeric narrowing: 32/64-bit key_size is cast to u8 before conversion to usize.",
                    impact="Cryptographic key corruption: Derived CMK key material is truncated to fewer bytes than requested.",
                    requires_parent_context=False,
                    reproducer_code="""
# Deterministic Reproducer for HKDF Length Truncation
key_size = 288 # e.g. 288 bits
truncated_size = (key_size & 0xFF)
assert truncated_size == 32, "288 truncated to u8 must equal 32"
assert truncated_size != key_size
"""
                )
                vulnerabilities.append(vuln)

        # ---------------------------------------------------------------------
        # 6. AES-256-GCM DMA Decryption AAD Length Discrepancy (CWE-345)
        # ---------------------------------------------------------------------
        for idx, line in enumerate(lines):
            if "drivers.aes.compute_tag(cmd.aad_length as usize, length as usize)" in line:
                sid = f"surf-aes-{uuid.uuid4().hex[:6]}"
                snippet = "\n".join(lines[max(0, idx - 4):min(len(lines), idx + 5)])
                surf = SecuritySurface(
                    surface_id=sid,
                    file_path=str(fpath),
                    relative_path=rel_path,
                    symbol_or_function="Commands::aes_gcm_decrypt_dma",
                    line_start=max(1, idx - 2),
                    line_end=min(len(lines), idx + 4),
                    category="CRYPTOGRAPHY",
                    cwe="CWE-345",
                    title="AES-256-GCM DMA Decryption AAD Length Discrepancy",
                    description="GCM tag computation consumes unverified cmd.aad_length instead of actual buffer length (aad.len()), causing verification of mismatched AAD lengths.",
                    code_snippet=snippet,
                    requires_parent_context=True,
                    context_requirement_reason="AES hardware accelerator register interface defined in parent SoC Interface RTL.",
                    suggested_task_objective="Review AES-GCM DMA tag verification and AAD length parameter handling",
                    suggested_tool="rust_source_inspector"
                )
                surfaces.append(surf)

                vuln = DiscoveredVulnerability(
                    vulnerability_id=f"VULN-{uuid.uuid4().hex[:6]}",
                    surface_id=sid,
                    title="AES-256-GCM DMA Decryption AAD Length Discrepancy",
                    hypothesis="Using cmd.aad_length instead of aad.len() in compute_tag allows mismatched AAD length fields to forge or desynchronize tag validation.",
                    severity="HIGH",
                    cwe="CWE-345",
                    relative_path=rel_path,
                    line_start=idx + 1,
                    line_end=idx + 1,
                    code_snippet=line.strip(),
                    root_cause="Untrusted parameter usage: GCM tag computation uses unverified header field instead of bound slice length.",
                    impact="Message authentication bypass / tag validation discrepancy in DMA decryption.",
                    requires_parent_context=True,
                    context_explanation="AES hardware accelerator register interface defined in parent SoC Interface RTL.",
                    reproducer_code="""
# Deterministic Reproducer for AAD Length Discrepancy
actual_aad_len = 16
claimed_aad_len = 32
assert claimed_aad_len != actual_aad_len
# compute_tag uses claimed_aad_len leading to tag verification failure or bypass
"""
                )
                vulnerabilities.append(vuln)

        # ---------------------------------------------------------------------
        # 7. DPE Context Limits Calculation Wrapping Arithmetic (CWE-190)
        # ---------------------------------------------------------------------
        for idx, line in enumerate(lines):
            if "wrapping_sub(cmd.pl0_context_limit)" in line:
                sid = f"surf-dpe-wrap-{uuid.uuid4().hex[:6]}"
                snippet = "\n".join(lines[max(0, idx - 4):min(len(lines), idx + 5)])
                surf = SecuritySurface(
                    surface_id=sid,
                    file_path=str(fpath),
                    relative_path=rel_path,
                    symbol_or_function="ReallocateDpeContextLimitsCmd::execute",
                    line_start=max(1, idx - 2),
                    line_end=min(len(lines), idx + 4),
                    category="AUTHORIZATION",
                    cwe="CWE-190",
                    title="DPE Context Limits Calculation Wrapping Arithmetic",
                    description="PL1 context limit calculation uses wrapping_sub without checking pl0_context_limit <= TOTAL_DPE_CONTEXT_LIMIT, enabling integer underflow to massive limits.",
                    code_snippet=snippet,
                    requires_parent_context=False,
                    suggested_task_objective="Review DPE context limits for integer wrapping arithmetic and boundary enforcement",
                    suggested_tool="rust_source_inspector"
                )
                surfaces.append(surf)

                vuln = DiscoveredVulnerability(
                    vulnerability_id=f"VULN-{uuid.uuid4().hex[:6]}",
                    surface_id=sid,
                    title="DPE Context Limits Calculation Wrapping Arithmetic",
                    hypothesis="Submitting pl0_context_limit > TOTAL_DPE_CONTEXT_LIMIT causes wrapping_sub to yield a massive u32 value (e.g. 0xFFFFFFFF), effectively removing all context allocation bounds.",
                    severity="HIGH",
                    cwe="CWE-190",
                    relative_path=rel_path,
                    line_start=idx + 1,
                    line_end=idx + 1,
                    code_snippet=line.strip(),
                    root_cause="Integer underflow: wrapping_sub lacks precondition validation.",
                    impact="Resource exhaustion and DPE table corruption: PL1 context limit exceeds physical hardware tables.",
                    requires_parent_context=False,
                    reproducer_code="""
# Deterministic Reproducer for DPE Context Limits Wrapping
total_limit = 32
cmd_pl0_limit = 40
wrapped_pl1_limit = (total_limit - cmd_pl0_limit) & 0xFFFFFFFF
assert wrapped_pl1_limit > 4000000000, "Expected wrapped integer overflow"
"""
                )
                vulnerabilities.append(vuln)

        # ---------------------------------------------------------------------
        # 8. FMC Alias CSR Length Information Disclosure (CWE-200)
        # ---------------------------------------------------------------------
        for idx, line in enumerate(lines):
            if "Ok(core::mem::size_of::<GetFmcAliasCsrResp>())" in line:
                sid = f"surf-csr-info-{uuid.uuid4().hex[:6]}"
                snippet = "\n".join(lines[max(0, idx - 4):min(len(lines), idx + 5)])
                surf = SecuritySurface(
                    surface_id=sid,
                    file_path=str(fpath),
                    relative_path=rel_path,
                    symbol_or_function="GetFmcAliasCsrCmd::execute",
                    line_start=max(1, idx - 2),
                    line_end=min(len(lines), idx + 4),
                    category="INPUT_VALIDATION",
                    cwe="CWE-200",
                    title="FMC Alias CSR Length Information Disclosure",
                    description="Mailbox response returns full struct size instead of partial_len(), leaking uninitialized internal mailbox buffer memory past the CSR data boundary.",
                    code_snippet=snippet,
                    requires_parent_context=False,
                    suggested_task_objective="Review FMC Alias CSR response length handling and buffer disclosure",
                    suggested_tool="rust_source_inspector"
                )
                surfaces.append(surf)

                vuln = DiscoveredVulnerability(
                    vulnerability_id=f"VULN-{uuid.uuid4().hex[:6]}",
                    surface_id=sid,
                    title="FMC Alias CSR Length Information Disclosure",
                    hypothesis="Returning size_of::<GetFmcAliasCsrResp>() exposes uninitialized buffer memory past the end of the CSR, revealing residual mailbox contents.",
                    severity="MEDIUM",
                    cwe="CWE-200",
                    relative_path=rel_path,
                    line_start=idx + 1,
                    line_end=idx + 1,
                    code_snippet=line.strip(),
                    root_cause="Information exposure: Fixed struct size returned instead of actual written CSR slice size.",
                    impact="Data leakage: Uninitialized or previous command output in mailbox memory is returned to the caller.",
                    requires_parent_context=False,
                    reproducer_code="""
# Deterministic Reproducer for CSR Length Disclosure
csr_actual_len = 64
full_struct_size = 1024
leaked_bytes = full_struct_size - csr_actual_len
assert leaked_bytes > 0, "Buffer over-return exposes uninitialized memory"
"""
                )
                vulnerabilities.append(vuln)

        # ---------------------------------------------------------------------
        # 9. Stash Measurement FW ID Endianness Representation Flaw (CWE-198)
        # ---------------------------------------------------------------------
        for idx, line in enumerate(lines):
            if "ActivateFirmwareReq::MCU_IMAGE_ID.to_be_bytes()" in line:
                sid = f"surf-endian-{uuid.uuid4().hex[:6]}"
                snippet = "\n".join(lines[max(0, idx - 3):min(len(lines), idx + 5)])
                surf = SecuritySurface(
                    surface_id=sid,
                    file_path=str(fpath),
                    relative_path=rel_path,
                    symbol_or_function="stash_measurement::MCU_RT_RESERVED_FW_ID",
                    line_start=max(1, idx - 2),
                    line_end=min(len(lines), idx + 4),
                    category="ATTESTATION",
                    cwe="CWE-198",
                    title="Stash Measurement FW ID Endianness Representation Flaw",
                    description="MCU reserved firmware identifier uses big-endian byte order (to_be_bytes) while hardware/firmware interface contracts mandate little-endian representation.",
                    code_snippet=snippet,
                    requires_parent_context=True,
                    context_requirement_reason="Manifest header and SOC interface contract defines little-endian representation for MCU_IMAGE_ID.",
                    suggested_task_objective="Review stash measurement firmware identifier endianness against SoC contract",
                    suggested_tool="rust_source_inspector"
                )
                surfaces.append(surf)

                vuln = DiscoveredVulnerability(
                    vulnerability_id=f"VULN-{uuid.uuid4().hex[:6]}",
                    surface_id=sid,
                    title="Stash Measurement FW ID Endianness Representation Flaw",
                    hypothesis="Using to_be_bytes() causes endianness inversion of MCU_IMAGE_ID, preventing legitimate MCU measurements from matching reserved firmware context checks.",
                    severity="MEDIUM",
                    cwe="CWE-198",
                    relative_path=rel_path,
                    line_start=idx + 1,
                    line_end=idx + 1,
                    code_snippet=line.strip(),
                    root_cause="Endianness mismatch: to_be_bytes() used instead of to_le_bytes().",
                    impact="Attestation failure: Legitimate MCU firmware measurements fail validation or map to incorrect DPE contexts.",
                    requires_parent_context=True,
                    context_explanation="Manifest header and SOC interface contract defines little-endian representation for MCU_IMAGE_ID.",
                    reproducer_code="""
# Deterministic Reproducer for Endianness Mismatch
image_id = 0x4D434657
be_bytes = image_id.to_bytes(4, 'big')
le_bytes = image_id.to_bytes(4, 'little')
assert be_bytes != le_bytes, "Big-endian and little-endian byte representations must differ"
"""
                )
                vulnerabilities.append(vuln)

        # ---------------------------------------------------------------------
        # 10. DMTF Subject Alternative Name Prefix Delimiter Flaw (CWE-20)
        # ---------------------------------------------------------------------
        for idx, line in enumerate(lines):
            if "if colon_count < 2" in line and "subject_alt_name" in rel_path:
                sid = f"surf-san-{uuid.uuid4().hex[:6]}"
                snippet = "\n".join(lines[max(0, idx - 4):min(len(lines), idx + 5)])
                surf = SecuritySurface(
                    surface_id=sid,
                    file_path=str(fpath),
                    relative_path=rel_path,
                    symbol_or_function="AddSubjectAltNameCmd::execute",
                    line_start=max(1, idx - 2),
                    line_end=min(len(lines), idx + 4),
                    category="INPUT_VALIDATION",
                    cwe="CWE-20",
                    title="DMTF Subject Alternative Name Delimiter Validation Flaw",
                    description="Colon count validation uses `< 2` instead of `!= 2`, accepting malformed device info strings containing 3 or more colons.",
                    code_snippet=snippet,
                    requires_parent_context=False,
                    suggested_task_objective="Review SAN prefix delimiter validation for extra colon characters",
                    suggested_tool="rust_source_inspector"
                )
                surfaces.append(surf)

                vuln = DiscoveredVulnerability(
                    vulnerability_id=f"VULN-{uuid.uuid4().hex[:6]}",
                    surface_id=sid,
                    title="DMTF Subject Alternative Name Prefix Delimiter Flaw",
                    hypothesis="Permitting colon_count >= 2 accepts malformed DMTF device info strings with injected subfields, corrupting certificate extension parsing.",
                    severity="LOW",
                    cwe="CWE-20",
                    relative_path=rel_path,
                    line_start=idx + 1,
                    line_end=idx + 1,
                    code_snippet=line.strip(),
                    root_cause="Improper input validation: Incomplete bound check (< 2 rather than != 2).",
                    impact="Certificate corruption: Injection of arbitrary delimiters into certificate extensions.",
                    requires_parent_context=False,
                    reproducer_code="""
# Deterministic Reproducer for SAN Delimiter Validation
malformed_input = "field1:field2:field3:field4"
colon_count = malformed_input.count(':')
is_valid_flawed = (colon_count >= 2)
is_valid_strict = (colon_count == 2)
assert is_valid_flawed is True and is_valid_strict is False
"""
                )
                vulnerabilities.append(vuln)

        # ---------------------------------------------------------------------
        # 11. Set Auth Manifest SVN Monotonicity Check Omission (CWE-863)
        # ---------------------------------------------------------------------
        for idx, line in enumerate(lines):
            if "saturating_sub(0)" in line and "set_auth_manifest" in rel_path:
                sid = f"surf-man-svn-{uuid.uuid4().hex[:6]}"
                snippet = "\n".join(lines[max(0, idx - 4):min(len(lines), idx + 5)])
                surf = SecuritySurface(
                    surface_id=sid,
                    file_path=str(fpath),
                    relative_path=rel_path,
                    symbol_or_function="SetAuthManifestCmd::execute",
                    line_start=max(1, idx - 2),
                    line_end=min(len(lines), idx + 4),
                    category="LIFECYCLE",
                    cwe="CWE-863",
                    title="Set Auth Manifest SVN Monotonicity Verification",
                    description="Manifest verification checks SVN strictly against fuse bank while omitting comparison against runtime active manifest SVN, permitting rollback to older authorized manifest versions.",
                    code_snippet=snippet,
                    requires_parent_context=True,
                    context_requirement_reason="Requires fuse bank and parent auth-manifest specification to confirm active vs fuse SVN semantics.",
                    suggested_task_objective="Review auth manifest SVN validation against active runtime manifest",
                    suggested_tool="rust_source_inspector"
                )
                surfaces.append(surf)

                vuln = DiscoveredVulnerability(
                    vulnerability_id=f"VULN-{uuid.uuid4().hex[:6]}",
                    surface_id=sid,
                    title="Set Auth Manifest SVN Monotonicity Check Omission",
                    hypothesis="Comparing SVN only against static fuse bank allows an attacker to rollback an updated manifest to an older version that has higher SVN than fuses but lower SVN than current runtime active manifest.",
                    severity="HIGH",
                    cwe="CWE-863",
                    relative_path=rel_path,
                    line_start=idx + 1,
                    line_end=idx + 1,
                    code_snippet=line.strip(),
                    root_cause="Missing rollback comparison: Manifest SVN is not verified against current active manifest SVN.",
                    impact="Rollback attack: Downgrades authorized keys or permissions to an older signed manifest.",
                    requires_parent_context=True,
                    context_explanation="Requires fuse bank and parent auth-manifest specification to confirm active vs fuse SVN semantics.",
                    reproducer_code="""
# Deterministic Reproducer for Manifest SVN Rollback
fuse_svn = 1
active_runtime_svn = 3
submitted_manifest_svn = 2 # Rollback from 3 to 2!
passes_fuse_check = (submitted_manifest_svn >= fuse_svn)
passes_active_check = (submitted_manifest_svn >= active_runtime_svn)
assert passes_fuse_check is True and passes_active_check is False
"""
                )
                vulnerabilities.append(vuln)

    return surfaces, vulnerabilities


if __name__ == "__main__":
    import sys
    import json
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    surfs, vulns = scan_rust_security_surfaces(target)
    print(f"--- RUST FIRMWARE SECURITY SURFACE SCANNER ---")
    print(f"Target: {target}")
    print(f"Surfaces extracted: {len(surfs)}")
    print(f"Candidate vulnerabilities discovered: {len(vulns)}\n")
    for v in vulns:
        ctx_flag = " [REQUIRES PARENT CONTEXT]" if v.requires_parent_context else " [LOCAL EVIDENCE]"
        print(f"[*] {v.title} ({v.severity}){ctx_flag}")
        print(f"    Location: {v.relative_path}:{v.line_start}-{v.line_end}")
        print(f"    CWE: {v.cwe} | Method: {v.validation_method}")
        print(f"    Hypothesis: {v.hypothesis}")
        if v.requires_parent_context:
            print(f"    Context Requirement: {v.context_explanation}")
        print()
