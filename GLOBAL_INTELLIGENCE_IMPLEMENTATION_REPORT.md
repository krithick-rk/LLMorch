# LLMorch Global Intelligence Plane Implementation Report

**Date:** 2026-09-24  
**Project:** LLMorch (`/home/hackdac/Desktop/intern/LLMorch`)  
**Architecture Layer:** Global Intelligence Plane (Phase 8 Foundation)  
**Status:** IMPLEMENTED  

---

## 1. Architectural Mission & Invariants

The Global Intelligence Plane is a structured, non-authoritative architectural layer that converts validated vulnerability research outcomes into reusable investigation guidance across heterogeneous hardware security codebases.

### Fundamental Invariants
1. **Non-Authoritative Boundary Invariant (Section 37):**
   - Global Intelligence answers *what to inspect, why it is interesting, which invariants apply, which tools collect required evidence, and which false positives resemble this*.
   - Global Intelligence **NEVER** issues a finding verdict or declares code vulnerable.
   - The **Validator** remains the sole terminal authority for `CONFIRMED`, `REJECTED`, or `INCONCLUSIVE` finding states.
2. **Multi-Representation Resilience (Section 38):**
   - Intelligence is captured across AST structural signatures, semantic security intent tokens, control-flow complexity, and behavioral state transition profiles.
   - It is strictly robust against renaming, formatting changes, and wrapper insertion.
3. **Privacy & Egress Enforcement (Section 43, 66–67):**
   - Raw project code, private keys, API credentials, and exact filepaths are strictly quarantined and never promoted to the global plane.
   - Egress policy defaults to `LOCAL_ONLY`.

---

## 2. Data Contracts & Model (`schemas/global_intelligence.py`)

The plane is founded on first-class Pydantic v2 schemas:

* **`SecurityConcept`**: Core architectural concepts and threat taxonomies (Root of Trust, Secure Boot, Bus Gating) with CWE references and provenance.
* **`SecurityInvariant`**: Formal and natural-language invariants (e.g. SVA properties for register lock immutability, DMA privilege checks).
* **`AttackSurfacePattern`**: Boundary archetypes (HW_SW_MMIO, MAILBOX_FIFO, JTAG) with entry points and common attack paths.
* **`VulnerabilityPattern`**: Multi-representation vulnerability archetypes with structural signatures, semantic intent tags, suggested investigation steps, and tool recommendations.
* **`FalsePositivePattern`**: Historical benign patterns (e.g. hardware shadow register double-latch) preventing repeat false alarms without blind suppression.
* **`ToolEvidencePattern`**: Mapping of vulnerability families to deterministic verification tools (SymbiYosys, Verilator, Cocotb) and required evidence artifacts (`trace.vcd`, `proof.smt2`).
* **`FeedbackRecord`**: First-class structured human review records with definitive labels (`CONFIRMED`, `FALSE_POSITIVE`, `MISSED_VULNERABILITY`, `WRONG_LOCALIZATION`, etc.).
* **`KnowledgePromotion`**: Controlled promotion records tracking project sanitization, acceptance status, and egress policy compliance.
* **`InvestigationContext`**: Structured, non-authoritative research guidance synthesized for agent consumption with mandatory invariant disclaimer.

---

## 3. Storage & Persistence (`intelligence/repository.py`, `history/database.py`)

Storage is backend-neutral, implemented on the existing SQLite engine with foreign key enforcement:
* `global_concepts`
* `security_invariants`
* `attack_surface_patterns`
* `vulnerability_patterns`
* `false_positive_patterns`
* `tool_evidence_patterns`
* `feedback_records`
* `knowledge_promotions`

All database interactions flow through `GlobalIntelligenceRepository`, preventing arbitrary SQL injection or unbounded mutation by LLM agents.

---

## 4. Controlled Service API (`intelligence/service.py`)

The service exposes bounded query surfaces:
* `retrieve(context: Dict[str, Any]) -> List[VulnerabilityPattern]`
* `explain_match(pattern_id: str) -> Dict[str, Any]`
* `get_guidance(analysis_unit_id: str, context: Optional[Dict]) -> InvestigationContext`
* `get_security_invariants(context: Dict[str, Any]) -> List[SecurityInvariant]`
* `get_historical_patterns(context: Dict[str, Any]) -> List[VulnerabilityPattern]`
* `get_false_positive_patterns(context: Dict[str, Any]) -> List[FalsePositivePattern]`
* `get_tool_guidance(context: Dict[str, Any]) -> List[ToolEvidencePattern]`
* `record_feedback(feedback: FeedbackRecord) -> str`
* `propose_update(outcome: Any, egress_policy: EgressPolicy) -> KnowledgePromotion`
* `promote_update(promotion_id: str) -> bool`

---

## 5. Obfuscation-Resilient Intelligence (`intelligence/obfuscation.py`)

To resist code refactoring, identifier renaming, and code formatting changes:
1. **AST Structural Fingerprinting:**
   - Pre-order traversal abstracting variable names, attributes, and constants into uniform `Operand` node types.
   - Context trivia (`Load`, `Store`, `Del`) is filtered out.
   - Produces deterministic, identical hashes across aggressive renaming (verified in `tests/test_obfuscation.py::test_ast_structural_fingerprint_across_renaming`).
2. **Semantic Intent Mapping:**
   - Normalized token multisets mapped to core security intents (`privilege`, `lock`, `crypto`, `boot`, `memory_safety`, `bus_interface`).
   - Weighted multi-factor similarity: containment overlap (0.50), Jaccard similarity (0.20), control-flow complexity match (0.20), and token overlap (0.10).

---

## 6. Human Feedback Loop & Learning Pipeline

1. **Human Review Capture:**
   - Analysts evaluate findings through `record_feedback()`.
   - Records reviewer identity, label (`FALSE_POSITIVE`, `CONFIRMED`, etc.), detailed rationale, corrected localization, and supporting evidence references.
2. **Learning Safety:**
   - Feedback modifies knowledge ranking, pattern confidence, and investigation strategy prioritization.
   - Feedback **never** weakens the Validator authority, sandbox isolation rules, or egress policy.
3. **Controlled Promotion:**
   - Research outcomes propose updates via `propose_update()`.
   - Sensitive tokens are stripped before insertion into global tables.
   - Enforces per-project `EgressPolicy` (`LOCAL_ONLY`, `TRUSTED_PROVIDER`, `RESTRICTED_EXTERNAL`, `NO_EXTERNAL_MODEL`).

---

## 7. Integration Matrix

* **With AnalysisUnit:** `get_guidance(analysis_unit_id)` binds scoped assets, trust boundaries, and precheck indicators to synthesize an `InvestigationContext`.
* **With Agents:** Agents receive high-signal guidance (invariants to check, attack paths to test) without receiving whole-repo dumps or unvetted historical assumptions.
* **With Tools:** `get_tool_guidance()` recommends deterministic EDA and verification tools based on vulnerability family.
* **With Validator:** The Validator remains completely independent. Global Intelligence does not influence or override validator reproduction or execution verdicts.

---

## 8. Verification & Test Evidence

All functionality is verified with executable tests:
* `tests/test_global_intelligence.py::test_global_intelligence_seeding` (PASS)
* `tests/test_global_intelligence.py::test_non_authoritative_guidance_invariant` (PASS)
* `tests/test_global_intelligence.py::test_explain_match_api` (PASS)
* `tests/test_global_intelligence.py::test_human_feedback_recording_first_class` (PASS)
* `tests/test_global_intelligence.py::test_privacy_filter_and_egress_policy_promotion` (PASS)
* `tests/test_obfuscation.py::test_comment_and_whitespace_invariance` (PASS)
* `tests/test_obfuscation.py::test_ast_structural_fingerprint_across_renaming` (PASS)
* `tests/test_obfuscation.py::test_semantic_signature_intent_retention_across_obfuscation` (PASS)
* `tests/test_obfuscation.py::test_wrapper_insertion_resilience` (PASS)
