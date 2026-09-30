<p align="center">
  <strong>🧠 LLMorch</strong><br>
  <em>Autonomous Multi-Agent SoC Vulnerability Research &amp; Verification Intelligence Platform</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-green?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18+-61DAFB?logo=react&logoColor=black" alt="React 18+">
  <img src="https://img.shields.io/badge/Vite-4.5+-646CFF?logo=vite&logoColor=white" alt="Vite">
  <img src="https://img.shields.io/badge/SQLite-WAL_Mode-003B57?logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Tests-434%20Passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Agentic Workflow](#agentic-workflow)
- [Directory Structure](#directory-structure)
- [Implementation Plan &amp; Phases](#implementation-plan--phases)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Frontend Console](#frontend-console)
- [Testing](#testing)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

**LLMorch** is an autonomous, multi-agent hardware security vulnerability research and SoC (System-on-Chip) verification intelligence platform. It orchestrates AI agents (Antigravity/AGY, Codex) with deterministic EDA/security tools (Verilator, Yosys, Cocotb, Semgrep) to perform automated vulnerability discovery, formal verification, and security policy generation across hardware designs and firmware codebases.

The platform transforms the traditional manual SoC verification process into a structured, evidence-based pipeline with full audit trail, deterministic reproducibility, and human-in-the-loop oversight.

### What makes LLMorch different?

- **Deterministic, not probabilistic**: Every finding is backed by reproducible tool evidence — exit codes, AST traces, formal proofs — not just LLM opinions.
- **23-Bucket SoC Ontology**: A comprehensive verification taxonomy covering every domain from IP boundaries to clock domain crossings to boot security.
- **Strict agent governance**: Only permitted agents (AGY, Codex) execute. Claude is registered for catalog awareness but blocked from execution by policy.
- **Human-in-the-loop**: Analysts approve verification plans, review work packages, and guide remediation — the system never silently modifies target repositories.

---

## Key Features

| Feature | Description |
|---|---|
| **Supervisor Strategic Planner** | Synthesizes versioned `VerificationPlan` objects with budget and cost gates from repository analysis |
| **Central Orchestrator** | Authoritative runtime engine managing task lifecycle, watchdog stall detection, and attempt lineage |
| **23-Bucket SoC Ontology** | Complete verification taxonomy (IP Boundary, CDC, RDC, Security, Boot, Memory, Closure, etc.) |
| **15 Dynamic Agent Roles** | Specialist profiles (Threat Modeling, CDC/RDC, Vulnerability Research, etc.) dynamically assigned per task |
| **Deterministic Tool Plane** | Sandboxed execution of Verilator, Yosys, Cocotb, Semgrep, Surfer, Z3 with structured JSON evidence |
| **Context Fabric** | Token-bounded graph context assembly scoped to specific tasks, roles, and buckets |
| **Evidence &amp; Validator Pipeline** | Deduplication, invariant verification, and provenance tracking for all findings |
| **Closure Engine** | 23-bucket coverage tracking, gap registration, waiver management, and sign-off readiness |
| **Policy Generator** | SoCureLLM-inspired candidate security policies with provenance (never auto-applied) |
| **Repository Intelligence** | Deterministic preflight analysis, Rust/RTL security scanning, complexity classification |
| **Real-time WebSocket Events** | Live event streaming with monotonic connection IDs and bounded exponential backoff |
| **React Analyst Console** | Full-featured SPA with verification plan views, task DAGs, evidence explorer, and agentic workflow canvas |
| **Watchdog &amp; Remediation** | Stale heartbeat detection, timeout controls, and guided failure retries |
| **Token Budget Governance** | Per-task and per-plan token accounting with allocation limits |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ANALYST / USER INTERFACE                            │
│    React Console (Vite) · REST API · WebSocket Events · CLI                │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │     FastAPI Gateway (app.py)  │
                    │   25 REST Routers · OpenAPI   │
                    │   WebSocket Event Manager     │
                    └──────────────┬──────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
┌─────────▼─────────┐  ┌─────────▼─────────┐  ┌─────────▼─────────┐
│    SUPERVISOR      │  │    ORCHESTRATOR    │  │    SCHEDULER       │
│  Strategic Planner │  │  Runtime Authority │  │  Execution Policy  │
│  Plan Synthesis    │  │  Task Lifecycle    │  │  Agent Switching   │
│  Budget Gates      │  │  Watchdog/Stall    │  │  Model Routing     │
│  Replan Versioning │  │  Attempt Lineage   │  │  Failover Logic    │
└─────────┬─────────┘  └─────────┬─────────┘  └─────────┬─────────┘
          │                       │                       │
          └───────────┬───────────┴───────────┬───────────┘
                      │                       │
         ┌────────────▼──────────┐  ┌────────▼────────────┐
         │    AGENTIC LAYER      │  │   CONTEXT FABRIC     │
         │  AGY (Antigravity)    │  │  SoC Graph Assembly  │
         │  Codex (OpenAI)       │  │  Token-Bounded Packs │
         │  15 Dynamic Roles     │  │  Spec Ingestion      │
         │  Scoped Handoffs      │  │  Requirement Tracing │
         └────────────┬──────────┘  └────────┬────────────┘
                      │                       │
         ┌────────────▼───────────────────────▼────────────┐
         │           DETERMINISTIC TOOL PLANE               │
         │  Verilator · Yosys · Cocotb · Semgrep · Z3      │
         │  Rust Security Scanner · RTL Security Scanner    │
         │  Sandbox Isolation · Structured JSON Evidence    │
         └────────────────────────┬────────────────────────┘
                                  │
         ┌────────────────────────▼────────────────────────┐
         │         EVIDENCE & VALIDATION PIPELINE           │
         │  Evidence Deduplication · Validator Engine       │
         │  Reproducer Generation · Finding Dossiers       │
         └────────────────────────┬────────────────────────┘
                                  │
         ┌────────────────────────▼────────────────────────┐
         │           CLOSURE & POLICY ENGINE                │
         │  23-Bucket Coverage · Gap Tracking · Waivers    │
         │  Candidate Policy Generation (SoCureLLM)        │
         │  Sign-off Readiness · Formal Closure Snapshots  │
         └────────────────────────┬────────────────────────┘
                                  │
         ┌────────────────────────▼────────────────────────┐
         │              PERSISTENCE LAYER                   │
         │  SQLite (WAL Mode, Foreign Keys, Thread-Safe)   │
         │  CRUD Repositories · Schema Migrations          │
         │  Project Isolation · Run History                 │
         └─────────────────────────────────────────────────┘
```

---

## Agentic Workflow

The complete execution pipeline from project intake to verification closure:

```
USER/ANALYST
    │
    ▼
┌──────────┐     ┌────────────┐     ┌──────────────┐     ┌───────────────┐
│  Project  │────▶│ Preflight  │────▶│  Supervisor   │────▶│ Orchestrator  │
│  Intake   │     │  Audit     │     │  Plan Synth.  │     │  Dispatch     │
└──────────┘     └────────────┘     └──────────────┘     └───────┬───────┘
                                                                  │
                    ┌─────────────────────────────────────────────┤
                    │                                             │
              ┌─────▼─────┐                                ┌─────▼─────┐
              │   AGY      │◄─── Scoped Handoff ───────────│   Codex    │
              │ (Primary)  │     (Orchestrator-Mediated)   │(Secondary)│
              └─────┬─────┘                                └─────┬─────┘
                    │                                             │
              ┌─────▼──────────────────────────────────────────────▼─────┐
              │              DETERMINISTIC TOOL EXECUTION                 │
              │  ┌──────────┐ ┌───────┐ ┌───────┐ ┌────────┐ ┌────┐    │
              │  │Verilator │ │ Yosys │ │Cocotb │ │Semgrep │ │ Z3 │    │
              │  └──────────┘ └───────┘ └───────┘ └────────┘ └────┘    │
              └──────────────────────────┬──────────────────────────────┘
                                         │
              ┌──────────────────────────▼──────────────────────────────┐
              │                    EVIDENCE PLANE                       │
              │  Tool output hashes · Exit codes · AST traces          │
              │  Formal proofs · Simulation waveforms                   │
              └──────────────────────────┬──────────────────────────────┘
                                         │
              ┌──────────────────────────▼──────────────────────────────┐
              │               VALIDATOR & REPRODUCER                    │
              │  Invariant verification · PoC minimization              │
              │  Deterministic replay · Verdict: CONFIRMED / REJECTED  │
              └──────────────────────────┬──────────────────────────────┘
                                         │
              ┌──────────────────────────▼──────────────────────────────┐
              │                FINDING DOSSIER                          │
              │  Severity · CWE · Attack surface · Breadcrumb trace    │
              │  Linked evidence · Reproducer · Analyst review          │
              └──────────────────────────┬──────────────────────────────┘
                                         │
              ┌──────────────────────────▼──────────────────────────────┐
              │            CLOSURE & POLICY GENERATION                  │
              │  23-Bucket coverage snapshot · Gap registration         │
              │  Waiver management · Candidate security policies        │
              │  Sign-off readiness assessment                          │
              └─────────────────────────────────────────────────────────┘
```

### Task State Machine

Tasks flow through a rigorous, explicit state machine with watchdog controls:

```
CREATED → QUEUED → PLANNING → WAITING_FOR_CONTEXT → WAITING_FOR_AGENT → RUNNING
                                                                          │
                    ┌──────────────────┬──────────────────┬───────────────┤
                    ▼                  ▼                  ▼               ▼
                 PAUSED        WAITING_FOR_HUMAN      BLOCKED        SUCCEEDED
                    │                  │                  │
                    ▼                  ▼                  ▼
                CANCELLED          RUNNING            FAILED → [Retry] → QUEUED
                                                        │
                                                     REJECTED (Terminal)
```

**Failure Remediation Options:**
- `[Retry]` — Re-run with clean sandbox
- `[Change Tool]` — Switch to alternative tool (e.g., Verilator → Yosys)
- `[Change Method]` — Switch verification method (e.g., Simulation → Formal)
- `[Change Agent]` — Reassign to another permitted agent
- `[Add Instruction]` — Inject analyst guidance into next attempt
- `[Replan]` — Trigger Supervisor to revise the verification plan

---

## Directory Structure

```
LLMorch/
├── adapters/                    # Provider-neutral agent adapters
│   ├── base.py                  #   Abstract adapter interface
│   ├── agy_adapter.py           #   Antigravity (AGY) adapter
│   ├── codex_adapter.py         #   OpenAI Codex adapter
│   └── claude_adapter.py        #   Claude adapter (execution disabled by policy)
│
├── agents/                      # Agentic layer
│   └── roles.py                 #   15 dynamic specialist role profiles mapped to SoC buckets
│
├── analysis_units/              # Code analysis unit decomposition
│
├── api/                         # FastAPI backend
│   ├── app.py                   #   Application entry point & middleware
│   ├── models.py                #   API request/response models
│   ├── realtime.py              #   WebSocket event manager
│   ├── session.py               #   Session authentication
│   └── routers/                 #   25 REST API routers
│       ├── tasks.py             #     Task CRUD, lifecycle, diagnostics
│       ├── agents.py            #     Agent management & model assignment
│       ├── findings.py          #     Finding dossiers & severity tracking
│       ├── evidence.py          #     Evidence submission & deduplication
│       ├── runs.py              #     Run lifecycle (start/pause/resume/stop)
│       ├── supervisor.py        #     Verification plan proposals & approval
│       ├── closure.py           #     23-bucket closure snapshots & waivers
│       ├── policies.py          #     Candidate policy management
│       ├── specifications.py    #     RM/TRM specification ingestion
│       ├── context_fabric.py    #     Context graph & pack assembly
│       ├── projects.py          #     Project isolation & management
│       ├── repository.py        #     Repository intelligence & scanning
│       ├── tools.py             #     Tool execution history & status
│       ├── controls.py          #     Run control (pause/resume/emergency stop)
│       ├── analysis.py          #     Preflight analysis & intake
│       ├── timeline.py          #     Event timeline & audit log
│       ├── tokens.py            #     Token usage accounting
│       ├── models.py            #     LLM model registry
│       ├── settings.py          #     System settings & preferences
│       ├── validation.py        #     Evidence validation endpoints
│       ├── chat.py              #     Chat interface & messaging
│       ├── questions.py         #     Analyst Q&A system
│       ├── comma.py             #     Comma assistant endpoints
│       └── debug.py             #     Debug & diagnostic endpoints
│
├── benchmarks/                  # Performance benchmarking
│
├── closure/                     # Verification closure engine
│   └── engine.py                #   23-bucket coverage, gap tracking, waivers, sign-off
│
├── configs/                     # System configuration
│   ├── system.yaml              #   Global system settings
│   ├── agents.yaml              #   Agent definitions & capabilities
│   ├── tools.yaml               #   Tool configurations
│   ├── policies.yaml            #   Execution policies
│   └── manager.py               #   Configuration loading & validation
│
├── context_fabric/              # SoC context assembly
│   └── fabric.py                #   Token-bounded context packs per task/role/bucket
│
├── correlation/                 # Evidence correlation engine
│   └── engine.py                #   Cross-reference evidence, findings, and requirements
│
├── critic/                      # Adversarial critique layer (stub)
│
├── docs/                        # Documentation
│
├── dri/                         # Design Rule Intelligence (stub)
│
├── evaluation/                  # Benchmark oracle comparator
│   └── benchmark_oracle_comparator.py
│
├── evidence/                    # Evidence plane contracts
│
├── history/                     # Persistence layer (SQLite)
│   ├── database.py              #   Schema migrations, WAL mode, connection pooling
│   ├── id_service.py            #   Deterministic ID generation (PROJ-001-TASK-003)
│   ├── repositories.py          #   Phase 0-8 CRUD repositories
│   ├── soc_repositories.py      #   SoC verification entity repositories
│   ├── phase8_repositories.py   #   Phase 8 entity repositories
│   ├── phase9_repositories.py   #   Phase 9 entity repositories
│   ├── project_repository.py    #   Project isolation & management
│   ├── project_logger.py        #   Structured project event logging
│   └── log_retention.py         #   Log rotation & cleanup
│
├── intelligence/                # Global intelligence service
│   ├── service.py               #   Cross-project intelligence aggregation
│   ├── repository.py            #   Intelligence data persistence
│   └── obfuscation.py           #   Data obfuscation for privacy
│
├── llmorch/                     # CLI entry point
│   ├── cli.py                   #   Command-line interface (doctor, agents, config, version)
│   └── __main__.py              #   `python -m llmorch` entry
│
├── memory/                      # Memory & knowledge management
│   ├── service.py               #   Memory service for agent context
│   ├── fingerprint.py           #   Content fingerprinting
│   ├── promotion.py             #   Finding promotion pipeline
│   └── applicability.py         #   Applicability assessment
│
├── orchestrator/                # Central runtime orchestrator
│   ├── orchestrator.py          #   Plan activation, task dispatch, watchdogs, lineage
│   ├── state_machine.py         #   Run state machine (IDLE/RUNNING/PAUSED/STOPPED)
│   ├── strategy.py              #   Execution strategy selection
│   ├── investigation.py         #   Deep investigation workflows
│   ├── tool_router.py           #   Dynamic tool routing per scope
│   └── stall_detector.py        #   Stall detection & recovery
│
├── policy/                      # Security policy generation
│   └── generator.py             #   SoCureLLM-inspired candidate policy engine
│
├── registry/                    # Entity registries
│   ├── agent_registry.py        #   Agent registration & capability matching
│   ├── model_registry.py        #   LLM model registry & routing
│   └── tool_registry.py         #   Verification tool registry
│
├── repository_intelligence/     # Repository analysis engine
│   ├── preflight.py             #   Deterministic preflight feasibility audit
│   ├── rust_security_scanner.py #   Rust codebase security surface scanner
│   ├── rtl_security_scanner.py  #   RTL (Verilog/VHDL) security scanner
│   ├── classifier.py            #   File type classification
│   ├── complexity.py            #   Complexity tier assessment
│   ├── scanner.py               #   General repository scanner
│   ├── intake.py                #   Repository intake pipeline
│   ├── token_estimator.py       #   Token cost estimation
│   ├── symbol_extractor.py      #   Code symbol extraction
│   ├── dependency_graph.py      #   Dependency graph builder
│   ├── family.py                #   Repository family detection
│   └── context.py               #   Repository context assembly
│
├── reproducers/                 # PoC reproducer engine
│   ├── generator.py             #   Reproducer generation from findings
│   └── minimizer.py             #   Reproducer minimization
│
├── sandbox/                     # Sandboxed tool execution
│   ├── runner.py                #   Isolated process runner
│   └── workspace.py             #   Workspace management
│
├── scheduler/                   # Execution scheduling
│   ├── execution_policy.py      #   Strict agent permission policy
│   ├── scheduler.py             #   Task scheduling engine
│   ├── agent_switcher.py        #   Dynamic agent role switching
│   ├── model_router.py          #   Model selection routing
│   └── failover.py              #   Failover & recovery logic
│
├── schemas/                     # Pydantic data contracts (35 schema files)
│   ├── soc_ontology.py          #   23-Bucket SoC verification taxonomy
│   ├── soc_verification.py      #   VerificationPlan, WorkPackage, Specification, etc.
│   ├── task_lifecycle.py        #   Task state machine, watchdog config, attempt records
│   ├── agent.py                 #   Agent schemas
│   ├── finding.py               #   Finding & vulnerability schemas
│   ├── evidence.py              #   Evidence schemas
│   ├── event.py                 #   Event & timeline schemas
│   ├── run.py                   #   Run lifecycle schemas
│   └── ... (27 more)            #   Token, memory, sandbox, reproducer, etc.
│
├── scripts/                     # Utility & verification scripts
│   ├── check_environment.py     #   System environment health check
│   ├── run_real_caliptra_benchmark.py  # Caliptra benchmark runner
│   └── verify_final_e2e_workflow.py    # End-to-end verification script
│
├── specifications/              # Specification ingestion
│   └── ingest.py                #   RM/TRM/SVD/Header ingestion & claim extraction
│
├── supervisor/                  # Strategic planning layer
│   └── supervisor.py            #   Plan synthesis, 23-bucket mapping, cost estimation
│
├── tests/                       # Test suite (42 test files, 434+ tests)
│   ├── test_soc_verification.py #   19 dedicated SoC verification tests
│   ├── test_phase9_*.py         #   Phase 9 API, controls, realtime tests
│   ├── test_elastic_agents.py   #   1-4 elastic agent model tests
│   └── ... (39 more)            #   Full regression suite
│
├── token_tracker/               # Token budget accounting
│   ├── accounting.py            #   Usage tracking & reporting
│   ├── allocator.py             #   Budget allocation per task/plan
│   └── limits.py                #   Limit enforcement & alerts
│
├── tools/                       # Verification tool integration
│   ├── runner.py                #   Deterministic tool execution engine
│   └── precheck.py              #   Tool availability validation
│
├── ui/                          # React frontend (Vite)
│   ├── src/
│   │   ├── App.jsx              #   Main SPA with routing & sidebar
│   │   ├── api.js               #   REST API client
│   │   ├── realtimeClient.js    #   WebSocket client (stable state machine)
│   │   ├── index.css            #   Enterprise EDA workstation theme
│   │   └── components/          #   30+ React components
│   │       ├── AgenticWorkflow/ #     Interactive React Flow canvas
│   │       ├── VerificationPlan/#     Plan viewer with work packages
│   │       ├── Closure/         #     23-bucket coverage dashboard
│   │       ├── Specifications/  #     Spec ingestion & requirements
│   │       ├── Policies/        #     Policy candidate management
│   │       ├── Tools/           #     Tool execution explorer
│   │       ├── Repository/      #     Repository intelligence viewer
│   │       ├── Findings/        #     Finding dossier & evidence
│   │       └── ContextFabric/   #     Context graph visualizer
│   └── vite.config.js           #   Vite configuration
│
├── validator/                   # Evidence validation engine
│   ├── engine.py                #   Invariant verification engine
│   └── service.py               #   Validation service & verdicts
│
├── workspaces/                  # Project workspace storage
├── pyproject.toml               # Python project metadata
└── state.db                     # Runtime state database
```

---

## Implementation Plan &amp; Phases

### Phase 0 — Contract Freeze &amp; Foundation ✅
> Established machine-readable data contracts, state machines, agent abstractions, adapter boundaries, persistence models, and configuration infrastructure.

- Pydantic schemas for all entities (tasks, findings, evidence, agents)
- SQLite persistence with WAL mode, foreign keys, thread-safe access
- Agent registry with capability matching
- Provider-neutral adapter pattern (AGY, Codex, Claude)
- CLI entry point (`python -m llmorch`)

### Phase 1–4 — Intelligence Layers ✅
> Repository scanning, file classification, complexity analysis, and security surface detection.

- Repository intelligence with AST-based analysis
- File classification (RTL, firmware, software, specs)
- Security surface builder and symbol extraction
- Dependency graph construction

### Phase 5–6 — Memory &amp; Correlation ✅
> Cross-finding correlation, memory fingerprinting, knowledge promotion pipeline.

- Memory service with content fingerprinting
- Finding promotion from candidate → confirmed
- Evidence correlation engine
- Applicability assessment

### Phase 7–8 — Reproducer &amp; Validator ✅
> Deterministic reproducer generation, PoC minimization, and formal validation.

- Reproducer generator and minimizer
- Validator engine with invariant checking
- Sandbox workspace isolation
- Structured evidence extraction

### Phase 9.1 — API &amp; Console Foundation ✅
> FastAPI REST + WebSocket API, React console, session management.

- 25 REST API routers with OpenAPI documentation
- WebSocket event streaming with stable state machine
- React SPA with enterprise EDA workstation theme
- Session authentication and CORS configuration

### Phase 9.2 — Run Control &amp; State Machine ✅
> Run lifecycle management with pause/resume/stop/emergency controls.

- Run state machine (IDLE → RUNNING → PAUSED → STOPPED)
- Human-in-the-loop pause gates
- Emergency stop with immediate task termination
- Run event history and audit trail

### Phase 9.3 — Agentic Workflow Visualization ✅
> Interactive React Flow canvas for orchestration visualization.

- Node types: Project, Supervisor, Orchestrator, WorkPackage, Task, Agent, Tool, Evidence, Finding, Closure
- Clickable nodes with live inspector panel
- Status filtering and search
- Communication protocol stream viewer

### Phase 9.4 — Task Lifecycle &amp; Watchdogs ✅
> Explicit task state machine with watchdog stall detection and guided remediation.

- 15-state task lifecycle with legal transition enforcement
- Watchdog heartbeat monitoring (90s stale threshold)
- Timeout budgets per task and per plan
- Actionable failure remediation controls

### Phase 9.5 — Human-in-the-Loop &amp; Controls ✅
> Analyst oversight with approval gates, instruction injection, and replan triggers.

- WorkPackage approve/reject controls
- Analyst instruction injection into task attempts
- Supervisor replan versioning (v1 → v2)
- Task priority and constraint management

### Phase 9.6 — Live Integration &amp; SoC Views ✅
> Full SoC verification architecture with 23-bucket ontology integration.

- Verification Plan page with work package breakdown
- Context Fabric page with component graph
- Specifications page with claim extraction
- Security Policies page with candidate management
- 23-Bucket Closure page with coverage gauges and waivers

### SoC Verification Architecture — Final Migration ✅
> Complete platform transformation from ad-hoc LLM runner to authoritative SoC verification intelligence platform.

- 23-Bucket SoC ontology with recommended roles and tools per bucket
- 15 dynamic specialist role profiles
- Deterministic preflight audit (zero-cost empty repository handling)
- Supervisor plan synthesis with execution recommendations
- Central Orchestrator with complete attempt lineage
- Closure engine with formal coverage snapshots
- SoCureLLM-inspired policy generation
- 434/434 tests passing (100% success rate)

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** (for frontend)
- **SQLite 3.35+** (bundled with Python)

### Installation

```bash
# Clone the repository
git clone https://github.com/krithick-rk/LLMorch.git
cd LLMorch

# Install Python dependencies
pip install -e .

# Install frontend dependencies
cd ui && npm install && cd ..
```

### Running the Backend

```bash
# Start the FastAPI server
python3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000

# API Base URL: http://127.0.0.1:8000/
# OpenAPI Docs: http://127.0.0.1:8000/api/docs
# WebSocket:    ws://127.0.0.1:8000/ws/events
```

### Running the Frontend

```bash
cd ui
npm run dev

# Opens at http://localhost:5173/
# Proxies API requests to http://127.0.0.1:8000/
```

### CLI Commands

```bash
# Check system status
python -m llmorch doctor

# View configured agents
python -m llmorch agents

# View active system configuration
python -m llmorch config

# View version information
python -m llmorch version
```

### Running Tests

```bash
# Run the complete test suite (434 tests)
pytest -q

# Run the dedicated SoC verification suite (19 tests)
pytest tests/test_soc_verification.py -v

# Run a specific phase test
pytest tests/test_phase9_1.py -v
```

---

## API Reference

The platform exposes 25 REST API routers. Full interactive documentation is available at `/api/docs` when the server is running.

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | System health check |
| `GET` | `/api/session` | Current session info |
| **Projects** | | |
| `GET` | `/api/projects` | List all projects |
| `POST` | `/api/projects` | Create new project with repository |
| `GET` | `/api/projects/{id}` | Project details |
| **Tasks** | | |
| `GET` | `/api/tasks` | List tasks (filterable by project, status) |
| `POST` | `/api/tasks` | Create new task |
| `GET` | `/api/tasks/{id}` | Task detail with attempt history |
| `GET` | `/api/tasks/{id}/diagnostics` | Failure diagnostics &amp; remediation options |
| **Runs** | | |
| `GET` | `/api/runs/current` | Current active run |
| `POST` | `/api/runs/{id}/pause` | Pause execution |
| `POST` | `/api/runs/{id}/resume` | Resume execution |
| `POST` | `/api/runs/{id}/stop` | Stop execution |
| `POST` | `/api/runs/{id}/emergency-stop` | Emergency stop (immediate) |
| **Verification** | | |
| `GET` | `/api/supervisor/plans` | List verification plans |
| `POST` | `/api/supervisor/propose` | Propose new verification plan |
| `POST` | `/api/supervisor/approve/{id}` | Approve plan for execution |
| `GET` | `/api/closure/{plan_id}` | Closure snapshot for plan |
| **Evidence &amp; Findings** | | |
| `GET` | `/api/evidence` | List evidence items |
| `POST` | `/api/evidence` | Submit new evidence |
| `GET` | `/api/findings` | List findings with severity |
| `GET` | `/api/findings/stats` | Finding statistics |
| **Agents** | | |
| `GET` | `/api/agents` | List registered agents |
| `GET` | `/api/agents/{id}` | Agent detail with capabilities |

### WebSocket

```
ws://127.0.0.1:8000/ws/events?project_id={id}&run_id={id}
```

Events: `TASK_CREATED`, `TASK_STARTED`, `TASK_COMPLETED`, `TOOL_STARTED`, `TOOL_COMPLETED`, `EVIDENCE_SUBMITTED`, `FINDING_CREATED`, `PLAN_APPROVED`, `RUN_STATE_CHANGED`

---

## Frontend Console

The React console provides a full-featured analyst workstation:

| Page | Route | Description |
|------|-------|-------------|
| **Project Home** | `/` | Project overview with metrics and activity |
| **Tasks** | `/tasks` | Task list with status, priority, and lifecycle controls |
| **Task Detail** | `/task/{id}` | Full task console with attempts, tools, evidence, and remediation |
| **Agentic Workflow** | `/workflow` | Interactive React Flow canvas showing orchestration DAG |
| **Agents** | `/agents` | Agent status, roles, and model assignments |
| **Verification Plan** | `/verification-plan` | Plan revisions, work packages, 23-bucket scope |
| **Context Fabric** | `/context-fabric` | Component graph, interfaces, security assets |
| **Specifications** | `/specifications` | RM/TRM documents, extracted claims &amp; requirements |
| **Security Policies** | `/policies` | Candidate policy cards with sign-off status |
| **23-Bucket Closure** | `/closure` | Coverage gauges, gap tracking, waiver management |
| **Evidence** | `/evidence` | Evidence explorer with validation status |
| **Findings** | `/findings` | Finding dossiers with severity and trace |
| **Run History** | `/runs` | Run timeline with event audit trail |
| **Tools** | `/tools` | Tool execution history and output viewer |
| **Settings** | `/settings` | System, agent, and model configuration |

---

## Testing

The test suite consists of **434+ tests** across 42 test files:

| Suite | Tests | Description |
|-------|-------|-------------|
| `test_soc_verification.py` | 19 | SoC verification pipeline end-to-end |
| `test_elastic_agents.py` | 25+ | 1-4 elastic agent execution model |
| `test_phase9_*.py` | 80+ | Phase 9 API, controls, realtime, E2E |
| `test_phase1-8.py` | 100+ | Foundation through validator phases |
| `test_execution_policy.py` | 10+ | Strict agent permission enforcement |
| `test_sandbox_hardening.py` | 15+ | Sandbox isolation and security |
| `test_project_isolation.py` | 12+ | Multi-project data isolation |
| Others | 170+ | Schemas, CLI, adapters, state machines, etc. |

### Key Acceptance Tests

- **Test 46** — Empty repository intake terminates immediately (0 tokens, 0 tasks, <10ms)
- **Test 47** — Single agent (AGY) completes entire verification plan end-to-end without secondary agent

---

## Configuration

### System Configuration (`configs/system.yaml`)

```yaml
system:
  name: LLMorch
  version: 0.1.0
  environment: development
  database:
    path: history/llmorch.db
    wal_mode: true
  api:
    host: 127.0.0.1
    port: 8000
```

### Agent Configuration (`configs/agents.yaml`)

```yaml
agents:
  - agent_id: agent-agy-01
    name: Antigravity (AGY)
    provider: antigravity
    enabled: true
    executable: true
  - agent_id: agent-codex-01
    name: Codex (OpenAI)
    provider: openai
    enabled: true
    executable: true
  - agent_id: agent-claude-01
    name: Claude Code
    provider: anthropic
    enabled: false          # Registered but execution DISABLED by policy
    executable: false
```

### Execution Policy

The execution policy is enforced in `scheduler/execution_policy.py`:

| Agent | Registered | Executable | Policy |
|-------|-----------|------------|--------|
| AGY (Antigravity) | ✅ | ✅ | Primary executor |
| Codex (OpenAI) | ✅ | ✅ | Secondary executor |
| Claude Code | ✅ | ❌ | Catalog awareness only, execution blocked |

---

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/your-feature`)
3. Run the test suite (`pytest -q`)
4. Commit your changes (`git commit -m 'Add your feature'`)
5. Push to the branch (`git push origin feature/your-feature`)
6. Open a Pull Request against `develop`

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>Built for hardware security research and SoC verification intelligence.</strong><br>
  <em>LLMorch — Deterministic. Auditable. Human-in-the-Loop.</em>
</p>
