"""
LLMorch Reproducer Minimization Engine (Phase 8)
Reduces test cases, inputs, and stimuli while preserving failure reproduction.
Guarantees:
- Original artifact A is always retained as baseline.
- Minimized artifact B is flagged as unverified until independently confirmed by the Validator.
- If minimized artifact B fails reproduction, the Validator retains original artifact A.
"""

import hashlib
import re
from typing import Dict, Any, Optional, Tuple

from schemas.validation import MinimizationResult


class MinimizationEngine:
    """
    Minimizes code, inputs, and stimuli for compact reproduction.
    Does not issue verdicts or authoritative confirmations.
    """

    @classmethod
    def minimize_python_script(cls, source_code: str) -> Tuple[str, float]:
        """
        Removes non-essential comments, docstrings, blank lines, and debug prints
        while preserving trigger logic and assertions.
        """
        lines = source_code.splitlines()
        retained = []
        for line in lines:
            stripped = line.strip()
            # Strip pure comment lines (except directives)
            if stripped.startswith("#") and not stripped.startswith("#!"):
                continue
            # Strip debug prints
            if stripped.startswith("print(") and "ASSERT" not in stripped and "TRIGGER" not in stripped:
                continue
            if not stripped:
                continue
            retained.append(line)

        minimized = "\n".join(retained) + "\n"
        orig_len = max(len(source_code), 1)
        min_len = len(minimized)
        reduction = max(0.0, float((orig_len - min_len) / orig_len) * 100.0)
        return minimized, reduction

    @classmethod
    def minimize_c_code(cls, source_code: str) -> Tuple[str, float]:
        """
        Minimizes C/C++ harness by stripping block comments and extraneous lines.
        """
        # Strip block comments /* ... */
        cleaned = re.sub(r'/\*.*?\*/', '', source_code, flags=re.DOTALL)
        lines = cleaned.splitlines()
        retained = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            if not stripped:
                continue
            retained.append(line)

        minimized = "\n".join(retained) + "\n"
        orig_len = max(len(source_code), 1)
        min_len = len(minimized)
        reduction = max(0.0, float((orig_len - min_len) / orig_len) * 100.0)
        return minimized, reduction

    @classmethod
    def minimize_stimulus(cls, stimulus: str) -> Tuple[str, float]:
        """
        Minimizes payload/input bytes or string.
        """
        lines = [l.strip() for l in stimulus.splitlines() if l.strip()]
        minimized = "\n".join(lines) + "\n"
        orig_len = max(len(stimulus), 1)
        min_len = len(minimized)
        reduction = max(0.0, float((orig_len - min_len) / orig_len) * 100.0)
        return minimized, reduction

    @classmethod
    def create_minimization_record(
        cls,
        original_content: str,
        minimized_content: str,
        reduction_percentage: float
    ) -> MinimizationResult:
        """
        Creates an unverified MinimizationResult record.
        The Validator MUST independently re-verify the minimized artifact before acceptance.
        """
        orig_hash = hashlib.sha256(original_content.encode("utf-8")).hexdigest()
        min_hash = hashlib.sha256(minimized_content.encode("utf-8")).hexdigest()
        return MinimizationResult(
            original_hash=orig_hash,
            minimized_hash=min_hash,
            original_size=len(original_content),
            minimized_size=len(minimized_content),
            reduction_percentage=round(reduction_percentage, 2),
            reproduction_verified_by_validator=False,
            retained_artifact_hash=orig_hash # Baseline retained until validator confirms
        )

    @classmethod
    def minimize_reproducer(cls, source_code: str, domain: str = "python") -> Dict[str, Any]:
        """Convenience method returning structured minimization summary dict."""
        if "c" in domain.lower():
            min_code, red = cls.minimize_c_code(source_code)
        elif "stim" in domain.lower():
            min_code, red = cls.minimize_stimulus(source_code)
        else:
            min_code, red = cls.minimize_python_script(source_code)

        orig_len = len(source_code)
        min_len = len(min_code)
        return {
            "original_content": source_code,
            "minimized_content": min_code,
            "original_size": orig_len,
            "minimized_size": min_len,
            "reduction_percentage": red,
            "original_hash": hashlib.sha256(source_code.encode("utf-8")).hexdigest(),
            "minimized_hash": hashlib.sha256(min_code.encode("utf-8")).hexdigest()
        }
