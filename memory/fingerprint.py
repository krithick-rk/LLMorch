"""
LLMorch Memory System - Deterministic Fingerprinting Engine (Phase 6)
Computes structural, semantic, and feature signatures for cross-project pattern matching.
"""

import re
import hashlib
from typing import List, Dict, Any


class FingerprintEngine:
    """
    Computes deterministic structural signatures, semantic fingerprints,
    and feature hashes for vulnerability patterns and analysis units.
    """

    @staticmethod
    def compute_structural_signature(domain: str, indicators: List[str], constructs: List[str]) -> str:
        """
        Derives a deterministic SHA256 structural hash from domain, normalized indicators, and constructs.
        """
        norm_indicators = sorted(list(set(i.lower().strip() for i in indicators)))
        norm_constructs = sorted(list(set(c.lower().strip() for c in constructs)))
        payload = f"domain:{domain.lower()}|indicators:{','.join(norm_indicators)}|constructs:{','.join(norm_constructs)}"
        return f"struct-{hashlib.sha256(payload.encode()).hexdigest()[:16]}"

    @staticmethod
    def compute_semantic_signature(text: str) -> str:
        """
        Strips project-specific paths, IDs, line numbers, and whitespace to form a normalized semantic signature.
        """
        # Remove file paths, hex addresses, line numbers
        cleaned = re.sub(r'/[^\s]+', '[PATH]', text)
        cleaned = re.sub(r'0x[0-9a-fA-F]+', '[HEX]', cleaned)
        cleaned = re.sub(r'line\s+\d+', '[LINE]', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b[a-f0-9]{8,64}\b', '[HASH]', cleaned)
        cleaned = " ".join(cleaned.lower().split())
        return f"sem-{hashlib.sha256(cleaned.encode()).hexdigest()[:16]}"

    @staticmethod
    def extract_features(text: str) -> List[str]:
        """
        Extracts key security keywords/indicators from text.
        """
        security_terms = [
            "privilege", "lock", "write_enable", "bounds_check", "null_pointer",
            "buffer_overflow", "auth_bypass", "race_condition", "use_after_free",
            "validation", "sanitization", "untrusted_input", "access_control",
            "memory_leak", "reentrancy", "integer_overflow", "register_write"
        ]
        text_lower = text.lower()
        found = [term for term in security_terms if term in text_lower]
        return sorted(found)
