# LLMorch — Phase 0 Implementation & Contract Freeze Report

## 1. Executive Summary

Phase 0 establishes the contract freeze and foundational architecture for LLMorch, a multi-agent hardware and software security research orchestrator. The primary objective of Phase 0 is to define machine-readable Pydantic schemas, state machines, agent abstractions, provider-neutral adapters, configuration management, SQLite persistence, and diagnostic tooling so that Phase 1 and subsequent phases can be built without altering fundamental data contracts.

## 2. Directory Baseline Audit

- Root directory: `/home/hackdac/Desktop/intern/LLMorch`
- Preserved existing items: `LICENSE`, `scripts/fix_antigravity_inline_ai.py`
- Added Phase 0 modules and contract packages across: `schemas/`, `orchestrator/`, `adapters/`, `registry/`, `history/`, `configs/`, `llmorch/`, `docs/`, `tests/`, and functional baseline modules for `scheduler/`, `evidence/`, `sandbox/`, `tools/`, `repository_intelligence/`, `analysis_units/`, `security_surface/`, `reproducers/`, `validator/`, `correlation/`, `critic/`, `benchmarks/`, `artifacts/`.

## 3. Data Contracts Frozen

The following 15 Pydantic contracts were frozen with strict validation, `schema_version = "1.0.0"`, enums, and timestamp fields:
1. **Task Contract** (`schemas/task.py`): Durable unit of work independent of model/provider.
2. **Run Contract** (`schemas/run.py`): Single execution attempt of a task.
3. **Agent Contract** (`schemas/agent.py`): Independent agent identity (`agent-agy-01`), provider, interface, health, quota.
4. **Capability Model** (`schemas/capability.py`): Data-driven capabilities (`repository_analysis`, `rtl_analysis`, `debugging`, etc.).
5. **Agent Health / Quota Contract** (`schemas/health.py`): Health states (`AVAILABLE`, `BUSY`, `UNAVAILABLE`, `DEGRADED`, `QUOTA_LIMITED`, `OFFLINE`, `AUTH_REQUIRED`, `ERROR`) and explicit quota handling without faked values.
6. **Checkpoint Contract** (`schemas/checkpoint.py`): Task state snapshot enabling a new agent to resume work without requiring prior conversation history.
7. **Artifact Contract** (`schemas/artifact.py`): Stored execution artifacts with cryptographic hashes.
8. **Evidence Contract** (`schemas/evidence.py`): Objective evidence records distinguishing agent claims from tool outputs and validator results.
9. **Finding Contract** (`schemas/finding.py`): Vulnerability findings and hypotheses owned by orchestrator state transitions.
10. **Analysis Unit Contract** (`schemas/analysis_unit.py`): Granular code/RTL scopes preventing full repository dumps to agents.
11. **Security Surface Contract** (`schemas/security_surface.py`): Trust boundaries, assets, privilege levels, entry points, and invariants.
12. **Event Contract** (`schemas/event.py`): Structured append-only audit event log.
13. **Agent Selection Contract** (`schemas/agent_selection.py`): Request/Response payload models for dynamic agent matching.
14. **1–4 Agent Policy Contract** (`schemas/policy.py`): Configuration for single, 2, 3, or 4 agent operational modes.
15. **Error Taxonomy & Exception Hierarchy** (`schemas/errors.py`): Structured error codes (`AGENT_UNAVAILABLE`, `QUOTA_EXHAUSTED`, `ADAPTER_FAILURE`, etc.).

## 4. State Machines

- **Task State Machine**: `QUEUED` → `DISPATCHED` → `RUNNING` → (`WAITING` / `SUCCEEDED` / `FAILED` / `CANCELED` / `BLOCKED`). Terminal states (`SUCCEEDED`, `FAILED`, `CANCELED`) cannot be transitioned out of.
- **Finding State Machine**: `HYPOTHESIS` → `REVIEWED` → `CORROBORATED` / `CONTRADICTED` → `VALIDATION_PENDING` → `CONFIRMED` / `REJECTED`.

## 5. Persistence Foundation

SQLite relational database implementation (`history/database.py`) enforcing foreign keys (`PRAGMA foreign_keys = ON;`) and providing transactional repository services (`TaskRepository`, `AgentRepository`, `RunRepository`, `CheckpointRepository`, `EventRepository`).

## 6. Configuration & CLI

- YAML Configuration files (`configs/system.yaml`, `configs/agents.yaml`, `configs/policies.yaml`, `configs/tools.yaml`) managed via `ConfigManager`.
- CLI Entrypoint (`llmorch doctor`, `llmorch agents`, `llmorch config`, `llmorch version`).
