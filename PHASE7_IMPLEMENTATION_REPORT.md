# LLMorch Phase 7: Repository Intelligence, Relevance Filtering & AnalysisUnits

## PHASE 7 STATUS
```
Implementation:         COMPLETE
Repository Snapshot:    PASS
Classification:         PASS
Build Intelligence:     PASS
Symbol/Module Intel:    PASS
Dependency Graph:       PASS
Reachability:           PASS
Security Surface:       PASS
AnalysisUnits:          PASS
Relevance Engine:       PASS
Scoped Context:         PASS
Secret Boundary:        PASS
Symlink Safety:         PASS
Phase 6 Integration:    PASS
Phase 5 Regression:     PASS
Tests:                  PASS
```

---

## 1. Architecture Diagram

```
                    Repository
                        │
                        ▼
               Repository Snapshot
               (archive_hash, per-file hashes, git_commit)
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
    File Classification      Build/Metadata
    (PRIMARY_SOURCE,         (Bazel, FuseSoC,
     GENERATED, VENDOR,       CMake, Cargo,
     SECRET, TEST, FORMAL)    Go modules, HJSON)
            │                       │
            └───────────┬───────────┘
                        ▼
              Symbol / Module Model
              (C/C++, Go, Java, Python, RTL)
                        │
                        ▼
             Dependency / Reachability
             (DIRECT, INFERRED, HEURISTIC)
             (REACHABLE, LIKELY, POSSIBLY, UNREACHABLE)
                        │
                        ▼
                 Security Surface
                 (Assets, TrustBoundary, AttackerCapability,
                  EntryPoints, Countermeasures, Properties)
                        │
                        ▼
                 AnalysisUnit (first-class)
                 (RTL Module / Bazel Target /
                  HW-SW Contract / Package Cluster)
                        │
                        ▼
                Relevance Engine
                (transparent score weights, PriorityLevel)
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
       Cheap Checks          Phase 6 Memory
       (precheck findings)   (pattern retrieval against AU scope)
             │                     │
             └──────────┬──────────┘
                        ▼
              Scoped Agent Context
              (secrets excluded, vendor excluded,
               generated excluded, 1-hop expansion with audit)
                        │
                        ▼
                   Agent Layer
                        │
                        ▼
                 Evidence / Tools
                        │
                        ▼
                    Validator
```

---

## 2. Repository Intelligence Pipeline (9 Layers)

| Layer | Module | Description |
|---|---|---|
| 1 | `scanner.py` | Snapshot + Archive Hash + Per-file SHA-256 |
| 2 | `classifier.py` | Deterministic file classification (16 categories) |
| 3 | `build_system.py` | Bazel, FuseSoC, CMake, Cargo, HJSON indexing |
| 4 | `symbol_extractor.py` | C/C++, Go, Java, Python, RTL symbols |
| 5 | `dependency_graph.py` | Dependency edges + BFS reachability hints |
| 6 | `security_surface_builder.py` | Assets, trust boundaries, countermeasures |
| 7 | `analysis_unit_builder.py` | First-class AnalysisUnit construction |
| 8 | `relevance.py` | Transparent scoring engine |
| 9 | `context.py` | Scoped agent context + 1-hop expansion audit |

---

## 3. File Classification Model

Supports 16 deterministic categories:
`PRIMARY_SOURCE`, `BUILD_METADATA`, `SECURITY_METADATA`, `GENERATED`, `VENDOR`, `THIRD_PARTY`, `TEST`, `FORMAL`, `DOCUMENTATION`, `SCRIPT`, `CONFIGURATION`, `CACHE`, `BUILD_OUTPUT`, `NOISE`, `SECRET`, `UNKNOWN`.

Classification uses: extension, directory role, file content, generator headers, vendor markers, secret patterns.

---

## 4. Secret & Symlink Safety

- **Secret Detection**: API keys, private keys, passwords, bearer tokens detected via regex. Files are classified `SECRET` and quarantined into `secrets_quarantine` DB table. They are **never** included in LLM agent context or Phase 6 global memory.
- **External Symlink Blocking**: Any symlink pointing outside the authorized repository root is detected, recorded as `EXTERNAL_BLOCKED`, and never followed. A `SYMLINK_BLOCKED` audit event is emitted.

---

## 5. AnalysisUnit Model

First-class strongly typed contract. Constructed from real security boundaries — **NOT** one-file-per-unit:
- **RTL Module Cluster**: SystemVerilog/Verilog module + associated ports, signals, always blocks
- **Bazel Target**: cc_library, cc_binary, py_library targets with source/dep lists
- **HW-SW Contract**: RTL register → HJSON → C header → DIF firmware driver
- **Language Package**: Python/Go/Java/C++ package or directory group

---

## 6. Relevance Engine

Transparent scoring with explicit weight components:

| Signal | Weight |
|---|---|
| Trust boundary present | +0.25 |
| Sensitive asset present | +0.20 |
| Reachable from entry point | +0.20 |
| Security property present | +0.15 |
| Countermeasure present | +0.10 |
| Entry point exposed | +0.10 |

Priority: `CRITICAL` (≥0.75) / `HIGH` (≥0.55) / `MEDIUM` (≥0.35) / `LOW` (≥0.15) / `IGNORE`.

> **CRITICAL DISTINCTION**: Priority = investigation resource allocation. It does NOT mean confirmed vulnerability.

---

## 7. Scoped Context Generation

The `AgentContextGenerator` enforces:
- ✅ Primary unit source files (filtered)
- ✅ Security surface summary
- ✅ Phase 6 memory pattern matches (scoped to AnalysisUnit)
- ✅ Cheap deterministic findings
- ❌ Secrets excluded
- ❌ Vendor code excluded by default
- ❌ Generated code excluded by default
- 🔍 1-hop dependency expansion: controlled, audited, with reason recorded in `context_expansions` table

---

## 8. Phase 6 Memory Integration

Memory retrieval now operates against scoped AnalysisUnit context (domain + indicators from security surface) rather than against the whole repository. This makes cross-project pattern matches genuinely useful and actionable.

---

## 9. Database Schema Changes (Phase 7)

New tables added (additive, non-destructive):
- `repository_snapshots`
- `source_files`
- `build_targets`
- `symbols`
- `dependencies`
- `hw_sw_contracts`
- `analysis_units` (extended Phase 7 schema)
- `security_surfaces` (extended Phase 7 schema)
- `secrets_quarantine`
- `context_expansions`

---

## 10. CLI Commands

```bash
python3 -m llmorch repo scan <repo-path>
python3 -m llmorch repo status <snapshot-id>
python3 -m llmorch repo units <snapshot-id>
python3 -m llmorch repo unit <analysis-unit-id>
python3 -m llmorch repo security-surface <unit-id>
python3 -m llmorch repo dependencies <unit-id>
python3 -m llmorch repo diff <snap-a> <snap-b>
```

---

## 11. Tests

`tests/test_phase7.py` covers 35+ tests:
- Repository snapshot identity + per-file hashes
- Incremental snapshot diff signals
- File classification (source, generated, vendor, secrets, tests)
- Build metadata detection (Bazel, HJSON)
- Symbol extraction (C/C++, Python, RTL modules)
- Dependency graph construction
- Reachability hint computation
- Security surface creation
- HW-SW contract detection
- AnalysisUnit construction (not file-per-unit)
- AnalysisUnit boundary integrity
- Relevance scoring and priority assignment
- Context generation scoping
- Vendor/generated/secrets excluded from agent context
- 1-hop expansion with audit
- Phase 6 memory integration via AnalysisUnit
- Snapshot diff signals (NEW, MODIFIED, UNCHANGED)
- Hard-negative (CRITICAL priority ≠ confirmed vulnerability)
- Performance (scan completes in <30s for test fixture)
- Phase 5 failover regression

---

## 12. Known Limitations

- RTL symbol extraction uses regex patterns rather than Slang/Verible AST integration (deterministic tooling interface is designed for pluggability in Phase 8)
- Call graph computation is import/include-based (not full AST call graph) — confidence labeled `HEURISTIC`/`INFERRED`
- HJSON parsing uses regex rather than a strict HJSON parser (pure Python HJSON library not assumed to be installed)
- Vector-based semantic similarity uses SHA-256 fingerprints rather than a vector database (Qdrant/Chroma interface is pluggable in future)

---

## 13. Recommended Phase 8 Work

- **Critic/Reproducer/Validator**: Structured multi-agent critic system that challenges hypotheses, constructs reproducers, and validates evidence
- **AST-precise symbol graphs**: Integrate Slang (RTL) and tree-sitter (C/Go/Python) for call-graph precision
- **Cross-snapshot regression detection**: Alert when previously-analyzed AnalysisUnit changes in ways that reopen closed findings
- **Analyst UI (Phase 9)**: Web interface exposing repository intelligence graph, AnalysisUnit explorer, memory pattern viewer
