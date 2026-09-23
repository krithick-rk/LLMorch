# LLMorch Phase 6: Cross-Project Intelligence & Persistent Research Memory Report

## 1. Executive Summary
Phase 6 establishes a durable, provider-agnostic, persistent research memory architecture for LLMorch.
The system allows LLMorch to retain reusable security-research knowledge across unrelated repositories while strictly preventing raw project source code, sensitive evidence, credentials, API keys, file paths, or repository identities from leaking into global memory.

---

## 2. Architecture Overview & ASCII Diagram

```text
               Project A / Project B Analysis Scope
                                │
                                ▼
                       Project Memory (Layer A)
                                │
                                ├──── Sensitive Artifact Store (Layer C)
                                │
                                └──── Promotion Gate (PromotionEngine)
                                          │
                                          ▼
                                Global Research Memory (Layer B)
                                          │
                                          ▼
                                  Retrieval Engine (MemoryService)
                                  (Deterministic-First: Exact > Struct > Feat > Sem)
                                          │
                                          ▼
                                LLM Applicability Check (LLMApplicabilityVerifier)
                                          │
                                          ▼
                                  Investigation Engine
                                          │
                                          ▼
                                 Validator (FindingValidator)
                                          │
                                          ▼
                                   Research Outcome
                                          │
                                          └────→ Project Memory (Layer A)
```

---

## 3. Core Architectural Layers
- **Layer A — Project Memory (`ProjectMemoryRecord`)**: Repository-scoped local memory containing local architecture facts, local findings, local rejected hypotheses, evidence references, and local analysis strategies. Marked `PROJECT_PRIVATE`.
- **Layer B — Global Research Memory (`PatternRecord`)**: Cross-project generalized security research patterns containing abstract structural signatures, semantic signatures, indicators, affected constructs, validation methods, and provenance. Marked `GLOBAL_GENERALIZED`.
- **Layer C — Sensitive Artifact Store**: Access-policy controlled project store holding raw tool outputs, source slices, waveforms, and credentials. Raw content is NEVER copied into global memory.

---

## 4. Privacy Model & Promotion Engine
The `PromotionEngine` (`memory/promotion.py`) evaluates project-local research outcomes for global promotion:
1. **Privacy Gate 1**: Checks generalizability flag and outcome confidence (`VALIDATED`).
2. **Privacy Gate 2 (Sanitization)**: Detects and redacts sensitive API keys, passwords, bearer tokens, certificates, emails, absolute Linux/Windows file paths, line numbers, and project directory names.
3. **Duplicate Pattern Merging**: Computes deterministic structural signatures (`FingerprintEngine`). If an equivalent pattern exists, updates observation count and merges new indicators without creating duplicate records.
4. **Audit Logging**: Emits `MEMORY_PROMOTION_PROPOSED`, `MEMORY_PROMOTION_ACCEPTED`, `MEMORY_PROMOTION_REJECTED`, and `MEMORY_PATTERN_MERGED` events.

---

## 5. First-Class `PatternRecord` Schema
```json
{
  "pattern_id": "pat-3f8a9b0c1d2e",
  "domain": "rtl",
  "title": "Generalized Privilege Lock Bit Pattern",
  "structural_signature": "struct-7f8a9b0c1d2e3f4a",
  "semantic_signature": "sem-1a2b3c4d5e6f7a8b",
  "indicators": ["lock_bit", "privilege_gating"],
  "affected_constructs": ["security_register"],
  "supporting_evidence_types": ["tool_output", "formal_proof"],
  "successful_analysis_steps": ["run_static_analysis", "construct_reproducer"],
  "rejected_analysis_steps": ["textual_name_search"],
  "validation_method": "FindingValidator",
  "provenance": {"domain": "rtl", "origin_project_hash": "sem-99887766"},
  "confidence_state": "VALIDATED",
  "privacy_class": "GLOBAL_GENERALIZED",
  "observation_count": 2,
  "version": 1,
  "schema_version": "1.0.0"
}
```

---

## 6. Deterministic-First Retrieval Order
The `MemoryService` (`memory/service.py`) retrieves candidates in strict deterministic-first priority:
1. `EXACT`: Structural signature hash match (Score: 1.0)
2. `STRUCTURAL`: Indicator set overlap match (Score: 0.70–0.95)
3. `FEATURE`: Security keyword extraction match (Score: 0.50–0.85)
4. `SEMANTIC`: Normalized semantic signature match (Score: 0.80)

---

## 7. LLM Applicability Verification Gate
The `LLMApplicabilityVerifier` (`memory/applicability.py`) evaluates retrieved patterns against target scope:
- Returns `ApplicabilityStatus` (`APPLICABLE`, `NOT_APPLICABLE`, `UNCERTAIN`).
- **CRITICAL GUARANTEE**: Does NOT declare code vulnerable or bypass the Validator. It only determines if the candidate pattern warrants targeted agent investigation.

---

## 8. Database Schema Extensions (`history/database.py`)
Created 5 SQLite relational tables:
- `project_memory`
- `global_patterns`
- `research_strategies`
- `research_outcomes`
- `memory_promotions`

---

## 9. CLI Subcommands (`llmorch/cli.py`)
```bash
# View memory system status & counts
python3 -m llmorch memory status

# List generalized global patterns
python3 -m llmorch memory list-global

# List repository-scoped project memory
python3 -m llmorch memory list-project <project-id>

# Inspect detailed PatternRecord JSON
python3 -m llmorch memory inspect <pattern-id>

# Search global patterns by context query
python3 -m llmorch memory search <query>
```

---

## 10. Cross-Project Security Boundary & Reuse Demo
- **Project A**: Analyzes target -> validates finding -> `PromotionEngine` sanitizes paths -> promotes `PatternRecord` to Global Memory.
- **Project B** (Unrelated project): `MemoryService.retrieve()` finds Project A's generalized pattern -> `LLMApplicabilityVerifier` confirms applicability -> agent investigates -> `FindingValidator` validates finding.
- **Project C** (Hard-negative case): `MemoryService.retrieve()` finds pattern -> `LLMApplicabilityVerifier` detects missing indicators (`NOT_APPLICABLE`) -> hypothesis rejected without false positives.

---

## 11. Verification & Test Suite (`tests/test_phase6.py`)
Passes 19 comprehensive unit & integration tests covering project scoping, global record generalization, sensitive artifact exclusion, path sanitization, structural fingerprinting, retrieval ordering, LLM applicability gate, false positive persistence, duplicate pattern merging, validator gate preservation, and Phase 5 failover regression compatibility.

---

## PHASE 6 STATUS
- **Implementation**: COMPLETE
- **Tests**: PASS
- **Cross-project demo**: PASS
- **Privacy boundary**: PASS
- **Phase 5 regression**: PASS
- **Known limitations**: Vector database (Qdrant/Chroma) backend is designed as an interface abstraction for future scaling; current implementation uses SQLite + deterministic fingerprinting.
- **Next recommended Phase 7 work**: Repository Intelligence (Decomposition into AnalysisUnits, Security Surface Modeling, AST Anchor Graphing).
