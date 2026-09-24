"""
LLMorch Global Intelligence - Obfuscation Resilience Module
Extracts structural, semantic, and boundary signatures that remain stable across
identifier renaming, comment removal, whitespace changes, and wrapper insertion.
"""

import ast
import re
import hashlib
from typing import List, Dict, Any, Optional
from schemas.global_intelligence import SemanticSignature, BehavioralSignature


class ObfuscationResilienceEngine:
    """
    Computes normalized structural fingerprints and semantic signatures
    that survive typical code transformations (refactoring, renaming, formatting).
    """

    SECURITY_INTENT_KEYWORDS = {
        "privilege": ["priv", "ring", "tier", "role", "admin", "cap", "permission"],
        "lock": ["lock", "freeze", "latch", "disable", "gate", "seal"],
        "crypto": ["aes", "sha", "hmac", "rsa", "key", "entropy", "seed", "nonce", "otp"],
        "boot": ["rom", "boot", "stage0", "bl0", "reset", "vector", "manifest"],
        "memory_safety": ["overflow", "bound", "limit", "dma", "offset", "alloc"],
        "state_transition": ["fsm", "state", "curr_state", "next_state", "transition"],
        "bus_interface": ["mmio", "axi", "apb", "tlul", "reg_we", "reg_re", "addr"]
    }

    @classmethod
    def normalize_tokens(cls, text: str) -> List[str]:
        """Strips comments, punctuation, and downcases alphanumeric tokens."""
        clean_text = re.sub(r"//.*|/\*[\s\S]*?\*/|#.*", "", text)
        raw_tokens = re.findall(r"[A-Za-z0-9_]{3,}", clean_text)
        return [t.lower() for t in raw_tokens]

    @classmethod
    def extract_intent_tags(cls, tokens: List[str]) -> List[str]:
        """Identifies security intents from normalized tokens."""
        detected = set()
        joined = " ".join(tokens)
        for intent, synonyms in cls.SECURITY_INTENT_KEYWORDS.items():
            if any(syn in joined for syn in synonyms):
                detected.add(intent)
        return sorted(list(detected))

    @classmethod
    def compute_ast_structural_fingerprint(cls, source_code: str, language: str = "python") -> str:
        """
        Extracts AST node hierarchy shape independent of identifier names and literal values.
        Normalizes variable names, constants, and attributes into generic Operands,
        and filters out syntax trivia context nodes (Load/Store/Del).
        """
        if language.lower() == "python":
            try:
                tree = ast.parse(source_code)
                node_types = []

                def visit(node):
                    if isinstance(node, ast.expr_context):
                        return
                    name = type(node).__name__
                    if name in ("Constant", "Name", "Attribute", "Num", "Str"):
                        name = "Operand"
                    node_types.append(name)
                    for child in ast.iter_child_nodes(node):
                        visit(child)

                visit(tree)
                seq_repr = ":".join(node_types[:250])
                return f"ast-{hashlib.sha256(seq_repr.encode()).hexdigest()[:16]}"
            except Exception:
                pass

        # Language fallback / generic structural extraction:
        syntax_tokens = re.findall(r"[{}(),;=+\-*/<>!&|^]|\b(?:if|else|while|for|return|switch|case|break|default)\b", source_code)
        seq_repr = "".join(syntax_tokens[:300])
        return f"struct-{hashlib.sha256(seq_repr.encode()).hexdigest()[:16]}"

    @classmethod
    def extract_semantic_signature(cls, source_code: str) -> SemanticSignature:
        """Constructs an obfuscation-resilient SemanticSignature."""
        tokens = cls.normalize_tokens(source_code)
        intents = cls.extract_intent_tags(tokens)

        # Retain canonical intent-bearing tokens
        canonical_tokens = set()
        for t in tokens:
            for syn_list in cls.SECURITY_INTENT_KEYWORDS.values():
                if any(syn in t for syn in syn_list):
                    canonical_tokens.add(t)

        # Complexity estimation
        branch_count = len(re.findall(r"\b(if|else|switch|case|while|for)\b", source_code))
        complexity = "LOW" if branch_count <= 2 else ("HIGH" if branch_count >= 8 else "MEDIUM")

        return SemanticSignature(
            intent_tags=intents,
            token_multiset=sorted(list(canonical_tokens))[:30],
            control_flow_complexity=complexity
        )

    @classmethod
    def compare_signatures(cls, sig_a: SemanticSignature, sig_b: SemanticSignature) -> float:
        """Computes similarity score between two semantic signatures (0.0 to 1.0)."""
        if not sig_a.intent_tags and not sig_b.intent_tags:
            return 0.5

        common_intents = set(sig_a.intent_tags) & set(sig_b.intent_tags)
        all_intents = set(sig_a.intent_tags) | set(sig_b.intent_tags)

        min_len = max(min(len(sig_a.intent_tags), len(sig_b.intent_tags)), 1)
        intent_overlap = len(common_intents) / min_len
        intent_jaccard = len(common_intents) / max(len(all_intents), 1)

        common_tokens = set(sig_a.token_multiset) & set(sig_b.token_multiset)
        all_tokens = set(sig_a.token_multiset) | set(sig_b.token_multiset)
        token_sim = (len(common_tokens) / max(len(all_tokens), 1)) if all_tokens else 0.5

        complexity_match = 1.0 if sig_a.control_flow_complexity == sig_b.control_flow_complexity else 0.5

        return (intent_overlap * 0.50) + (intent_jaccard * 0.20) + (complexity_match * 0.20) + (token_sim * 0.10)
