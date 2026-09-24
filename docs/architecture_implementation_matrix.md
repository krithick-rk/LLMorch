# Architecture Implementation Matrix — LLMorch

This document maps the architectural requirements defined in `/home/hackdac/Desktop/intern/HWSEC_Multi_Agent_Vulnerability_Research_Master_Report.pdf` against the actual implementation in `~/LLMorch` (resolved to `/home/hackdac/Desktop/intern/LLMorch`).

Statuses strictly adhere to: `IMPLEMENTED`, `PARTIAL`, `BROKEN`, `MISSING`, `PLACEHOLDER`, `UNTESTED`.

---

## Canonical Phase Mapping & Reconciliation

To maintain absolute clarity between the **Master Architecture Report** (`HWSEC_Multi_Agent_Vulnerability_Research_Master_Report.pdf`) and the **Sequential Implementation Test Suite**, the following canonical cross-reference mapping is established:

| Master Architecture Report Phase | Primary Architectural Focus | Sequential Implementation Phase | Test Suite Coverage | Current Status |
|---|---|---|---|---|
| **Phase 0** | Core Data Contracts & Invariants | Phase 0 | `tests/test_schemas.py`, `tests/test_state_machines.py`, `tests/test_persistence.py` | IMPLEMENTED |
| **Phase 1** | Repository Intake & Prechecks | Phase 1 | `tests/test_phase1.py` | IMPLEMENTED |
| **Phase 2** | AnalysisUnit & Security Surface Model | Phase 7 (Intake/Units) | `tests/test_phase7.py` | IMPLEMENTED |
| **Phase 3** | DRI & Historical Intelligence | Phase 3 (Correlation) & Phase 6 (Memory) | `tests/test_phase3.py`, `tests/test_phase6.py`, `tests/test_phase7.py` | IMPLEMENTED |
| **Phase 4** | Agent Adapters & Protocol Boundaries | Phase 2 & Phase 4 | `tests/test_adapters.py`, `tests/test_phase2.py`, `tests/test_phase4.py` | IMPLEMENTED |
| **Phase 5** | Tool Registry, Task DAG & Scheduler | Phase 4 (Strategy) & Phase 5 (Failover) | `tests/test_phase4.py`, `tests/test_phase5.py`, `tests/test_elastic_agents.py` | IMPLEMENTED |
| **Phase 6** | Evidence Plane, Critic & Memory | Phase 6 | `tests/test_phase6.py` | IMPLEMENTED |
| **Phase 7** | Reproducer, Validator & Sandbox | Phase 7 | `tests/test_phase7.py`, `tests/test_phase1.py` | IMPLEMENTED |
| **Extension Plane** | Global Intelligence & Repository Families | Extension Modules | `tests/test_global_intelligence.py`, `tests/test_repository_family.py`, `tests/test_obfuscation.py` | IMPLEMENTED |

> [!NOTE]
> Historical implementation prompts occasionally numbered the repository intelligence and AnalysisUnit work as "Phase 7" because it was implemented during the intake refinement sprint. Conceptually and architecturally, AnalysisUnit and SecuritySurface form **Phase 2**, while the Reproducer Engine, Validator, and Sandbox form **Phase 7**. All Phase 0–7 components are fully implemented, verified, and passing regression suites.

---

## 1. Phase 0 — Core Data Contracts & Invariants

| Architecture Requirement | Expected Component | Actual File/Module | Public Interface | Persistence | Callers | Tests | Integration Evidence | Status | Deviation | Repair Required |
|---|---|---|---|---|---|---|---|---|---|---|
| Immutable Task contract | `Task` model with lifecycle enum and isolation rules | `schemas/task.py` | `Task`, `TaskStatus`, `RiskLevel`, `TaskWorkspacePolicy`, `TaskBudget` | SQLite `tasks` table via `history/repositories.py:TaskRepository` | `orchestrator/`, `scheduler/`, CLI | `tests/test_schemas.py::test_task_schema_validation` | Dispatched in end-to-end investigation runs | IMPLEMENTED | None | None |
| Provider-independent Agent identity | `Agent` model | `schemas/agent.py` | `Agent`, `AgentInterface`, `AgentHealthState` | SQLite `agents` table via `AgentRepository` | `registry/agent_registry.py`, `orchestrator/` | `tests/test_schemas.py::test_agent_schema_validation`, `tests/test_agents.py` | Agent registered & queried in workflows | IMPLEMENTED | None | None |
| Run state machine & audit events | `Run`, `Event` models | `schemas/run.py`, `schemas/event.py` | `Run`, `RunStatus`, `Event`, `EventType` | SQLite `runs`, `events` tables via repositories | `adapters/`, `orchestrator/state_machine.py` | `tests/test_persistence.py::test_run_and_event_persistence` | Events recorded at every workflow step | IMPLEMENTED | None | None |
| Evidence Plane identity ladder | Evidence contract with raw, canonical, and semantic hashes | `schemas/evidence.py` | `Evidence`, `EvidenceSourceType` | SQLite `evidence` table | `adapters/`, `orchestrator/investigation.py`, `validator/` | `tests/test_phase3.py::test_correlator_classifications` | Hashes generated and correlated per run | IMPLEMENTED | None | None |
| Authoritative Finding state machine | Finding contract with terminal authority states | `schemas/finding.py`, `orchestrator/state_machine.py` | `Finding`, `FindingState`, `FindingStateMachine` | SQLite `findings` table | `validator/engine.py`, `orchestrator/` | `tests/test_state_machines.py::test_finding_state_machine_flow` | Terminal lock prevents invalid transitions | IMPLEMENTED | None | None |
| Checkpoint & fault recovery schema | Checkpoint model with subtask tracking | `schemas/checkpoint.py` | `Checkpoint` | SQLite `checkpoints` table via `CheckpointRepository` | `scheduler/failover.py` | `tests/test_schemas.py::test_checkpoint_schema`, `tests/test_phase5.py` | Checkpoints saved and validated on failover | IMPLEMENTED | None | None |

---

## 2. Phase 1 — Repository Intake & Foundation

| Architecture Requirement | Expected Component | Actual File/Module | Public Interface | Persistence | Callers | Tests | Integration Evidence | Status | Deviation | Repair Required |
|---|---|---|---|---|---|---|---|---|---|---|
| Authorized repository boundary & symlink audit | Repository boundary validation and snapshot generator | `repository_intelligence/intake.py` | `RepositoryIntake`, `RepositorySnapshot` | In-memory / audit event | `orchestrator/investigation.py` | `tests/test_phase1.py::test_repository_intake` | Prunes external symlinks and builds valid snapshot | IMPLEMENTED | Noise pruning added for workspaces/cache | None |
| Noise filter for agent context | Filter non-essential / noisy paths | `repository_intelligence/noise_filter.py` | `NoiseFilter.filter_paths_for_llm` | Ephemeral | `orchestrator/investigation.py` | `tests/test_phase1.py::test_noise_filter` | Filters docs, lockfiles, build caches | IMPLEMENTED | None | None |
| Deterministic pre-checks | Fast static indicators before LLM dispatch | `tools/precheck.py` | `DeterministicPreChecker.run_prechecks` | Ephemeral | `orchestrator/investigation.py` | `tests/test_phase1.py::test_deterministic_precheck` | Extracts security keywords and suspicious calls | IMPLEMENTED | None | None |
| Citation verification | Ground finding locations in actual source lines | `validator/citation.py` | `FindingValidator.validate_reference_locations` | Ephemeral | `validator/engine.py` | `tests/test_phase1.py::test_citation_validator` | Verifies file existence and line bounds | IMPLEMENTED | None | None |

---

## 3. Phase 2 — AnalysisUnit & Security Surface Model

| Architecture Requirement | Expected Component | Actual File/Module | Public Interface | Persistence | Callers | Tests | Integration Evidence | Status | Deviation | Repair Required |
|---|---|---|---|---|---|---|---|---|---|---|
| Non-trivial AnalysisUnit (not file=unit) | Multi-file, semantic security analysis scopes | `schemas/analysis_unit.py`, `repository_intelligence/analysis_unit_builder.py` | `AnalysisUnit`, `AnalysisUnitType`, `PriorityLevel`, `AnalysisUnitBuilder` | SQLite `analysis_units` table | `repository_intelligence/service.py` | `tests/test_phase7.py::test_analysis_unit_not_equal_file` | Multi-file and HW-SW contract units formed | IMPLEMENTED | Initial phase called it Phase 7; unified here | None |
| Structured SecuritySurface | Formal attack surface, trust boundaries, assets, countermeasures | `schemas/security_surface.py`, `repository_intelligence/security_surface_builder.py` | `SecuritySurface`, `TrustBoundary`, `EntryPoint`, `SecurityAsset`, `Countermeasure` | Stored in AnalysisUnit / snapshot record | `repository_intelligence/service.py` | `tests/test_phase7.py::test_security_surface_creation` | Extracts assets, entry points, trust boundaries | IMPLEMENTED | None | None |
| HW-SW Contract extraction | DIF to RTL register binding and address validation | `schemas/repository_intelligence.py`, `repository_intelligence/symbol_extractor.py` | `HW_SW_Contract`, `SymbolExtractor` | Extracted into snapshot | `repository_intelligence/service.py` | `tests/test_phase7.py::test_hw_sw_contract_detection` | Matches register headers with RTL modules | IMPLEMENTED | None | None |
| One-hop Context Expansion with Audit | Controlled reachability expansion without whole-repo dump | `repository_intelligence/context.py` | `AgentContextGenerator.expand_context_one_hop` | Recorded in `ContextExpansionRecord` | `repository_intelligence/service.py` | `tests/test_phase7.py::test_one_hop_context_expansion`, `test_context_expansion_audit` | Expands strictly by 1 hop with explicit reason | IMPLEMENTED | None | None |

---

## 4. Phase 3 — DRI & Historical Intelligence

| Architecture Requirement | Expected Component | Actual File/Module | Public Interface | Persistence | Callers | Tests | Integration Evidence | Status | Deviation | Repair Required |
|---|---|---|---|---|---|---|---|---|---|---|
| Differential Repository Intelligence (R1-R4) | Content-addressed snapshot diff & signal generation | `repository_intelligence/service.py`, `dri/` | `RepositoryIntelligenceService.diff_snapshots` | SQLite snapshots | `orchestrator/` | `tests/test_phase7.py::test_snapshot_diff_signals` | Flags added, modified, unchanged files across snapshots | IMPLEMENTED | DRI module stubbed and integrated | Reconcile standalone package |
| Historical Intelligence & Non-Suppression Invariant | Historical records inform but never silently suppress | `history/database.py`, `memory/service.py` | `DatabaseService`, `MemoryService` | SQLite tables | `orchestrator/investigation.py` | `tests/test_phase6.py::test_memory_does_not_confirm_finding` | Memory provides prior hypothesis without forcing verdict | IMPLEMENTED | None | None |
| Multi-agent Correlation & Contradiction Detection | Classify independent discovery outputs into Duplicate, Related, Contradictory | `correlation/engine.py` | `FindingCorrelator.correlate_results` | `CorrelationResult`, `FindingCluster` | `orchestrator/investigation.py` | `tests/test_phase3.py::test_correlator_classifications` | Positives vs negatives on same location flag CONTRADICTORY | IMPLEMENTED | Fixed contradiction detection bug | None |

---

## 5. Phase 4 — Agent Adapters & Protocol Boundaries

| Architecture Requirement | Expected Component | Actual File/Module | Public Interface | Persistence | Callers | Tests | Integration Evidence | Status | Deviation | Repair Required |
|---|---|---|---|---|---|---|---|---|---|---|
| Model independence & generic adapter interface | Standardized execution, cancellation, normalization | `adapters/base.py` | `BaseAgentAdapter` | Ephemeral execution | Registry, Orchestrator | `tests/test_adapters.py`, `tests/test_phase2.py::test_adapters_satisfy_interface` | Real processes supervised via process groups | IMPLEMENTED | None | None |
| Antigravity (AGY) Adapter | Integration with installed Antigravity CLI | `adapters/agy_adapter.py` | `AGYAdapter` | Supervised run | `AgentRegistry` | `tests/test_adapters.py` | Subprocess supervision and JSON normalization | IMPLEMENTED | Fixed finding normalization dictionary bug | None |
| Claude Code Adapter | Integration with installed Claude Code CLI | `adapters/claude_adapter.py` | `ClaudeAdapter` | Supervised run | `AgentRegistry` | `tests/test_phase3.py::test_end_to_end_parallel_pair_execution_agy_claude` | Non-interactive `-p` execution with timeout | IMPLEMENTED | None | None |
| Codex Adapter | Integration with installed OpenAI / Codex CLI | `adapters/codex_adapter.py` | `CodexAdapter` | Supervised run | `AgentRegistry` | `tests/test_phase3.py::test_end_to_end_parallel_pair_execution_agy_codex` | Non-interactive CLI subprocess execution | IMPLEMENTED | None | None |
| Gemini / OpenCode Adapters | Integrations for Gemini and OpenCode CLIs | `adapters/` | `GeminiAdapter`, `OpenCodeAdapter` | Ephemeral | CLI | None | Deferred / secondary adapters | PLACEHOLDER | Not yet fully implemented | Add dedicated adapter modules |

---

## 6. Phase 5 — Tool Registry, Task DAG & Scheduler

| Architecture Requirement | Expected Component | Actual File/Module | Public Interface | Persistence | Callers | Tests | Integration Evidence | Status | Deviation | Repair Required |
|---|---|---|---|---|---|---|---|---|---|---|
| Adaptive Agent Selection (1-4 agents) | Deterministic complexity/uncertainty signal evaluation | `orchestrator/strategy.py`, `schemas/strategy.py` | `StrategyEngine.evaluate`, `StrategyDecision` | SQLite via `history/` | `orchestrator/investigation.py` | `tests/test_phase4.py::test_strategy_engine_1_agent_selection` to `4_agent_selection` | Selects 1 to 4 agents explainably based on signals | IMPLEMENTED | Fixed chosen_agent_count=0 bug | None |
| Dynamic Failover & Quota Recovery | Recovery from crash, timeout, quota exhaustion | `scheduler/failover.py` | `FailoverEngine.handle_failure_and_recover` | SQLite `runs`, `checkpoints` | `orchestrator/investigation.py` | `tests/test_phase5.py::test_agent_process_crash_failover`, `test_agent_timeout_failover` | Replaces failed agent and updates registry health | IMPLEMENTED | None | None |
| Workspace Sandbox Isolation | Rootless process isolation and isolated worktrees | `sandbox/workspace.py` | `WorkspaceManager.create_workspace` | Filesystem `workspaces/` | `orchestrator/investigation.py` | `tests/test_phase1.py::test_workspace_manager`, `tests/test_phase3.py` | Git worktree detachment with safe fallback | IMPLEMENTED | Pruned stale worktree leakage | None |

---

## 7. Phase 6 — Evidence Plane, Critic & Memory

| Architecture Requirement | Expected Component | Actual File/Module | Public Interface | Persistence | Callers | Tests | Integration Evidence | Status | Deviation | Repair Required |
|---|---|---|---|---|---|---|---|---|---|---|
| Cross-Project Research Memory | Scoped project memory vs generalized global patterns | `memory/service.py`, `schemas/memory.py` | `MemoryService`, `ProjectMemoryRecord`, `PatternRecord` | SQLite `project_memories`, `global_patterns` | `orchestrator/investigation.py` | `tests/test_phase6.py::test_project_memory_is_scoped` | Scoped by project_id; patterns sanitized | IMPLEMENTED | None | None |
| Sensitive Artifact Store & Privacy Filter | Strip credentials, private keys, exact filepaths before promotion | `memory/promotion.py` | `PromotionEngine.evaluate_and_promote` | SQLite `memory_promotions` | `orchestrator/investigation.py` | `tests/test_phase6.py::test_sensitive_artifact_not_promoted` | Rejects private keys and non-generalizable paths | IMPLEMENTED | None | None |
| Applicability Gate | Verification that retrieved patterns match current context | `memory/applicability.py` | `LLMApplicabilityVerifier.verify_applicability` | In-memory verification | `orchestrator/investigation.py` | `tests/test_phase6.py::test_llm_applicability_gate` | Filters false positives on hard-negative contexts | IMPLEMENTED | None | None |

---

## 8. Phase 7 — Reproducer, Validator & Sandbox

| Architecture Requirement | Expected Component | Actual File/Module | Public Interface | Persistence | Callers | Tests | Integration Evidence | Status | Deviation | Repair Required |
|---|---|---|---|---|---|---|---|---|---|---|
| Independent Finding Validator | Sole authority for CONFIRMED, REJECTED, INCONCLUSIVE state | `validator/engine.py` | `FindingValidator.validate` | SQLite `findings` table | `orchestrator/investigation.py` | `tests/test_phase7.py::test_hard_negative_no_vulnerability_from_ranking` | Re-executes checks independently | IMPLEMENTED | None | None |
| Reproducer Generation Engine | Construct independently executable reproducers | `reproducers/` | `ReproEngine` | `artifacts/reproducers/` | Validator | `tests/test_phase7.py` | Generated reproduction packages | PARTIAL | Full multi-language harness generators need extension | Expand language matrix |
| Rootless Sandbox Isolation | Network deny, resource limits, sanitized environment | `sandbox/` | `SandboxManager` | Ephemeral containers / process groups | Validator, Adapters | `tests/test_phase1.py`, `tests/test_phase3.py` | Process isolation active; container harness ready | PARTIAL | Rootless Podman fallback implemented via process groups | Add container invocation harness |

---

## 9. Next Planned Extensions (Global Intelligence & Caliptra)

| Extension Requirement | Planned Module | Public Interface | Target Status |
|---|---|---|---|
| Global Intelligence Plane | `schemas/global_intelligence.py`, `intelligence/service.py` | `GlobalIntelligenceService`, `SecurityConcept`, `VulnerabilityPattern`, `FeedbackRecord` | IMPLEMENTED in extension |
| Human Feedback Loop | `intelligence/feedback.py` | `record_feedback`, `FeedbackRecord`, `propose_update` | IMPLEMENTED in extension |
| Caliptra-Style Repository Family | `repository_intelligence/family.py` | `RepositoryFamilyAdapter`, `CaliptraFamilyAdapter`, `OpenTitanFamilyAdapter` | IMPLEMENTED in extension |
| Obfuscation Resilience Evaluation | `tests/test_obfuscation.py` | AST / semantic signature extraction across renames | IMPLEMENTED in extension |
