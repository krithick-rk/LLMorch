"""
Controlled Evaluation Tests - Obfuscation Resilience (Section 61)
Evaluates AST structural fingerprints and semantic signature matching
across identifier renaming, comment removal, whitespace changes, and wrapper insertion.
"""

import pytest
from intelligence.obfuscation import ObfuscationResilienceEngine
from schemas.global_intelligence import SemanticSignature


ORIGINAL_CODE = """
def check_privilege_and_latch(req):
    # Verify caller privilege tier against register lock
    if req.privilege >= REQUIRED_TIER:
        if not reg_is_locked:
            write_register(req.offset, req.data)
            return True
    return False
"""

OBFUSCATED_RENAMED_CODE = """
def sub_8f91a(arg_01):
    if arg_01.priv >= 2:
        if not lock_active:
            reg_we(arg_01.off, arg_01.val)
            return True
    return False
"""

OBFUSCATED_WRAPPED_CODE = """
def check_privilege_and_latch(req):
    return _internal_latch_proxy(req)

def _internal_latch_proxy(r):
    if r.privilege >= REQUIRED_TIER:
        if not reg_is_locked:
            write_register(r.offset, r.data)
            return True
    return False
"""


def test_comment_and_whitespace_invariance():
    """Verifies tokens and structural signatures survive comment and whitespace removal."""
    code_with_comments = """
    # This is a critical security function
    /* multi-line comment block */
    def lock_gate():
        return True
    """
    code_stripped = "def lock_gate(): return True"

    tokens_a = ObfuscationResilienceEngine.normalize_tokens(code_with_comments)
    tokens_b = ObfuscationResilienceEngine.normalize_tokens(code_stripped)

    assert tokens_a == tokens_b
    assert "lock_gate" in tokens_a


def test_ast_structural_fingerprint_across_renaming():
    """
    Verifies that AST structural node hierarchy fingerprint is preserved
    even when identifiers and variable names are completely renamed.
    """
    fp_orig = ObfuscationResilienceEngine.compute_ast_structural_fingerprint(ORIGINAL_CODE, "python")
    fp_renamed = ObfuscationResilienceEngine.compute_ast_structural_fingerprint(OBFUSCATED_RENAMED_CODE, "python")

    # Both share identical AST node sequence: FunctionDef -> If -> If -> Return
    assert fp_orig == fp_renamed


def test_semantic_signature_intent_retention_across_obfuscation():
    """
    Verifies that abstract security intents (privilege, lock) are retained
    despite identifier renaming.
    """
    sig_orig = ObfuscationResilienceEngine.extract_semantic_signature(ORIGINAL_CODE)
    sig_renamed = ObfuscationResilienceEngine.extract_semantic_signature(OBFUSCATED_RENAMED_CODE)

    assert "privilege" in sig_orig.intent_tags
    assert "privilege" in sig_renamed.intent_tags
    assert "lock" in sig_orig.intent_tags
    assert "lock" in sig_renamed.intent_tags

    sim = ObfuscationResilienceEngine.compare_signatures(sig_orig, sig_renamed)
    assert sim >= 0.60, f"Expected signature similarity >= 0.60 across renaming, got {sim}"


def test_wrapper_insertion_resilience():
    """Verifies that wrapper insertion maintains high semantic similarity."""
    sig_orig = ObfuscationResilienceEngine.extract_semantic_signature(ORIGINAL_CODE)
    sig_wrapped = ObfuscationResilienceEngine.extract_semantic_signature(OBFUSCATED_WRAPPED_CODE)

    common_intents = set(sig_orig.intent_tags) & set(sig_wrapped.intent_tags)
    assert "privilege" in common_intents
    assert "lock" in common_intents
