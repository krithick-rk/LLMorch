# LLMorch — Architectural Decision Records (ADRs)

## ADR 001: Pydantic v2 Schema Standardization
- **Status**: Accepted
- **Context**: LLMorch requires strict, machine-readable data contracts across all system boundaries.
- **Decision**: All contracts (`Task`, `Run`, `Agent`, `Checkpoint`, `Artifact`, `Evidence`, `Finding`, `AnalysisUnit`, `SecuritySurface`, `Event`) use Pydantic BaseModel with strict validation, `schema_version = "1.0.0"`, enums, and explicit ISO-8601 timestamps.
- **Consequences**: Standardized serialization, automatic validation, and clear schema versioning.

## ADR 002: Provider-Neutral Agent Identity
- **Status**: Accepted
- **Context**: Legacy architectures hard-coded model roles (e.g., Claude=master, Codex=coder, Gemini=researcher).
- **Decision**: `agent_id` is an independent string (e.g. `agent-agy-01`). Roles and capabilities are assigned dynamically by the orchestrator based on data-driven capability tags.
- **Consequences**: Enables 1–4 elastic agent scaling and seamless failover.

## ADR 003: SQLite Foreign-Key Enforced Relational Persistence
- **Status**: Accepted
- **Context**: Phase 0 requires lightweight, durable persistence for workstation deployment without external service dependencies like PostgreSQL or Qdrant.
- **Decision**: SQLite with `PRAGMA foreign_keys = ON;` is used for single-workstation storage. Repositories manage transactional operations for tasks, runs, agents, events, and checkpoints.
- **Consequences**: Zero infrastructure footprint for Phase 0 while guaranteeing referential integrity.

## ADR 004: Checkpoint-Based Failover Architecture
- **Status**: Accepted
- **Context**: LLM context windows and agent availability fluctuate. When an agent fails, passing full conversation logs to a replacement agent is wasteful and fragile.
- **Decision**: Agents serialize completed/remaining subtasks, workspace snapshots, and finding references into structured `Checkpoint` objects. Replacement agents resume directly from checkpoints.
- **Consequences**: Clean agent handoff and resilience against quota or process failures.

## ADR 005: Local CLI Isolation vs A2A Boundary Definition
- **Status**: Accepted
- **Context**: AGY CLI is invoked locally via subprocess.
- **Decision**: Local CLI execution is handled via `AGYAdapter` and is NOT categorized as A2A federation. A2A is reserved strictly for distributed gateway-to-gateway agent communications.
- **Consequences**: Avoids confusing local adapter execution with network-level agent protocols.
