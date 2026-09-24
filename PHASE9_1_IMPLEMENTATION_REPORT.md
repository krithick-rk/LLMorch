# LLMorch — Phase 9.1 Implementation Report

**Title**: Analyst UI, Investigation Console, Dynamic Agent & Model Switching, Authoritative Token Accounting, and Repository Token Estimation  
**Repository**: `/home/hackdac/Desktop/intern/LLMorch`  
**Date**: September 24, 2026  
**Status**: Completed & Verified — 288/288 Unit & Regression Tests Passing + 4/4 End-to-End Tests Passing (0 Regressions)

---

## 1. Executive Summary

Phase 9.1 extends the LLMorch autonomous hardware security vulnerability research platform with an authoritative control plane and high-density analyst console. While Phase 9 established the initial FastAPI backend, WebSocket realtime bridge, and read-only React dashboard, Phase 9.1 delivers the operational interactivity required for enterprise hardware security investigations:

1. **Strict Separation of Agent Registry and Model Registry**: Decouples autonomous execution harnesses (adapters, CLI processes, permissions, workspaces) from underlying LLM inference engines (token limits, context windows, cost tiers, reasoning scores).
2. **Deterministic Agent & Model Switching**: Enables live switching of agents (manual analyst override, automatic failover) and models (`AUTO`, `MANUAL`, `POLICY` routing) with checkpoint preservation, run retirement, parent lineage tracking, and zero duplicate execution.
3. **Elastic Multi-Agent Invariant Preservation**: Preserves the verified elastic scaling rules ($1 \rightarrow 1$, $2 \rightarrow 2$, $3 \rightarrow 3$, $4 \rightarrow 4$, $0 \rightarrow \text{BLOCKED}$) without hardcoding team sizes.
4. **Authoritative Token Accounting Subsystem**: Implements actual vs. estimated token accounting, audit events, aggregate run/agent/model/stage summaries, and limits (`AVAILABLE`, `LOW`, `NEAR_LIMIT`, `EXHAUSTED`, `BLOCKED`).
5. **Pre-Dispatch Repository Token Estimator**: Analyzes repository structure, calculates raw disk footprint vs. LLM-scoped tokens, estimates stage breakdowns, computes language ratios, and quarantines secrets safely prior to model dispatch.
6. **Production Analyst UI Console**: Upgrades the React + Vite frontend with interactive agent switching dialogs, model binding modals, real SVG Task DAG with dependency edges, real SVG security repository graph, live Token Budget Dashboard, and an API-backed Settings & Policy screen with safe server-side masked secrets.
7. **Zero Regressions**: Maintains 100% test pass rate across all prior phases (Phases 0–9).

---

## 2. Separation of Agent Registry vs. Model Registry

In LLMorch Phase 9.1, **Agents** and **Models** are distinct architectural entities:

```text
┌────────────────────────────────────────────────────────┐
│                   Agent Registry                       │
│  - Instance IDs: agent-agy-01, agent-codex-01, etc.   │
│  - Adapters: CLI, Subprocess, API                      │
│  - Lifecycle: ACTIVE, BUSY, DEGRADED, BLOCKED          │
│  - Hardware Security Tools: verilator, yosys, etc.     │
│  - Supported Model IDs: ["gemini-2.5-pro", ...]        │
│  - Active Model Binding: current_model_id              │
└───────────────────────────┬────────────────────────────┘
                            │ Queries Capabilities & Routing
                            ▼
┌────────────────────────────────────────────────────────┐
│                   Model Registry                       │
│  - Model IDs: agy-pro-reasoner, o3-mini, sonnet, etc.  │
│  - Provider: antigravity, anthropic, openai, mock      │
│  - Capabilities: RTL_ANALYSIS, REPRODUCER_GEN, etc.    │
│  - Context Windows & Max Output Limits                 │
│  - Cost Tiers & Reasoning Scores                       │
│  - Selection Modes: AUTO, MANUAL, POLICY               │
└────────────────────────────────────────────────────────┘
```

### 2.1 Model Registry Implementation (`registry/model_registry.py`)
- **Metadata Registered**:
  - `agy-pro-reasoner`: Antigravity flagship reasoner, 1,000,000 token context, specialized for deep RTL and firmware cryptanalysis.
  - `agy-fast-triage`: Antigravity fast triage, 64,000 context, optimized for fast repository intake and mapping.
  - `claude-3-7-sonnet`: Anthropic hybrid reasoning, 200,000 context, general and security analysis.
  - `claude-3-5-haiku`: Anthropic fast triage, 128,000 context.
  - `o3-mini` & `o1`: OpenAI deep STEM/hardware reasoning, 128,000 context.
  - `gpt-4o`: OpenAI multi-modal analysis.
  - `mock-fast-model` & `mock-reasoner-model`: Deterministic offline models for testing.
- **Routing Engine (`scheduler/model_router.py`)**:
  - `AUTO`: Dynamically matches required capabilities (e.g., `rtl_analysis`, `reproducer_generation`) to the model with the lowest cost tier satisfying the capability set.
  - `POLICY`: Evaluates policy profiles (`balanced`, `fast_cost_effective`, `deep_security_reasoning`) to select the optimal model according to context requirements and cost constraints.
  - `MANUAL`: Binds explicitly specified model IDs chosen by the analyst.

---

## 3. Agent Switching & Failover Architecture

Agent switching allows transferring an in-flight or planned task from one agent to another without losing context or generating orphan runs.

```text
               Analyst Action OR Quota Exhaustion
                               │
                               ▼
                    [ Agent Switcher ]
                               │
      ┌────────────────────────┴────────────────────────┐
      ▼                                                 ▼
1. Validate Target Agent                      2. Checkpoint Active Run
   - Health == AVAILABLE                         - Persist Task Memory
   - Capabilities matched                        - Persist Artifacts/Evidence
   - Concurrency not exceeded                    - Mark Checkpoint VALID
      │                                                 │
      └────────────────────────┬────────────────────────┘
                               ▼
                    3. Retire Active Run
                       - Status -> CANCELLED
                       - Prevent Duplicate Execution
                               │
                               ▼
                    4. Bind Compatible Model
                       - ModelRouter validates target agent compatibility
                               │
                               ▼
                    5. Spawn Linked Child Run
                       - parent_run_id = retired_run.run_id
                       - status = RUNNING
                               │
                               ▼
                    6. Update Task & Audit
                       - assigned_agent_id = target_agent.id
                       - retry_count += 1
                       - Insert into agent_switches DB
                       - Broadcast AGENT_SWITCH_COMPLETED
```

### 3.1 Lineage & Zero Duplicate Execution
- **Run Status Retirement**: The prior run is transitioned to `RunStatus.CANCELLED` with execution supervisor termination before the replacement run is created.
- **Parent Lineage**: The new run explicitly stores `parent_run_id = previous_run.run_id`, forming a cryptographic/database-verifiable directed tree of execution attempts.
- **Checkpoint Validation**: `CheckpointRepository` persists artifacts and partial progress. When `resume_action == "RESUME_FROM_CHECKPOINT"`, the new run starts with the valid checkpoint ID.

---

## 4. Authoritative Token Accounting Subsystem

### 4.1 Core Components (`token_tracker/`)
- `TokenTracker` (`token_tracker/accounting.py`):
  - Records actual input/output tokens from adapter executions.
  - Tracks pre-dispatch estimated tokens.
  - Computes consumption ratios and accuracy metrics.
  - Emits `TOKEN_USAGE_RECORDED` audit events.
- `TokenBudgetAllocator` (`token_tracker/allocator.py`):
  - Enforces deterministic budget allocation across phases (Discovery, Deep Analysis, Validation).
  - Reserves 30% of total run budget for validator reproduction and confirmation.
- `TokenLimitEnforcer` (`token_tracker/limits.py`):
  - Evaluates limit statuses:
    - `AVAILABLE`: Usage $< 70\%$ of budget.
    - `LOW`: Usage $\ge 70\%$ and $< 90\%$.
    - `NEAR_LIMIT`: Usage $\ge 90\%$ and $< 100\%$.
    - `EXHAUSTED`: Usage $\ge 100\%$.
    - `BLOCKED`: Auto-stop triggered; all subsequent dispatches halt.

### 4.2 Database Persistence
Tables created in `history/database.py`:
- `token_usage`: Records individual token usage records (task_id, run_id, agent_id, model_id, actual/estimated tokens, stage, execution latency).
- `token_budgets`: Scoped budgets (`run`, `agent`, `model`, `task`, `phase`) with consumed tokens, remaining tokens, and status.
- `agent_switches`: Auditable log of all manual and failover agent switches.
- `model_switches`: Auditable log of all dynamic model rebindings.
- `repository_token_estimates`: Pre-dispatch estimation reports.
- `configuration_records`: Persistent analyst settings.

---

## 5. Pre-Dispatch Repository Token Estimator

Implemented in `repository_intelligence/token_estimator.py`:
- **Raw Disk Footprint vs. LLM-Scoped Tokens**:
  - Differentiates entire repository bytes from code relevant to hardware security analysis.
  - Evaluates character-to-token heuristic ratios by language (e.g., C/C++: 3.5 chars/tok, SystemVerilog: 3.2 chars/tok, Python: 3.6 chars/tok).
- **Secrets Quarantine Exclusion**:
  - Scans for files containing secrets (`.env`, `*secret*`, `*credential*`, `*id_rsa*`, `*token*`, `.pem`).
  - Quarantined secrets are excluded from LLM transmission and counted under `quarantined_secrets_count`.
- **Pipeline Stage Distribution**:
  - Discovery: 25%
  - Static Analysis: 30%
  - Deep Verification: 30%
  - Validation & Reproduction: 15%
- **Recommended Budget**: Computes recommended token budget factoring in a 30% reserve and estimation confidence score.

---

## 6. Frontend UI Enhancements (`ui/src/`)

### 6.1 Run Overview & Token Dashboard
- **Live Token Accounting Bar**: Color-coded progress bar displaying consumed tokens, remaining tokens, and limit status badges (`AVAILABLE`, `LOW`, `NEAR_LIMIT`, `EXHAUSTED`, `BLOCKED`).
- **Metric Cards**: Actual tokens consumed, estimated allocation, prompt/completion token ratio, accuracy ratio.
- **Consumption Breakdowns**: Tabular breakdown by Agent, Model, and Pipeline Stage.
- **Repository Token Estimator Modal**: Interactive path input triggering structured estimation, displaying raw vs. LLM-scoped tokens, secrets excluded, language distribution, and a "Apply Budget" action.

### 6.2 Upgraded Agent Panel
- **Rich Agent Cards**:
  - Agent ID, Provider, Interface, Role, Adapter version.
  - Status Badge (`ACTIVE`, `IDLE`, `SWITCHING`, `FAILOVER`) and Health Badge (`AVAILABLE`, `DEGRADED`, `BLOCKED`).
  - Active Model badge and supported model tags.
  - Switch and failover audit counters.
- **Interactive Modals**:
  - `AgentSwitchModal`: Select replacement agent from eligible registry pool, specify reason, and select resume strategy (`RESUME_FROM_CHECKPOINT`, `RETRY`, `PAUSE`).
  - `ModelSwitchModal`: Select compatible model from ModelRegistry, specify switch reason, and set scope (`CURRENT_TASK`, `FUTURE_TASKS`).
  - Enable/Disable agent toggle.

### 6.3 Real Interactive Task DAG (`ui/src/components/TaskDAGVisualizer.jsx`)
- Replaces static flex cards with an interactive SVG topological graph.
- Calculates node layout by dependency depth.
- Smooth SVG cubic bezier curves with directional arrowheads connecting predecessor tasks to dependent tasks.
- Interactive node inspector displaying task metadata, active model, token consumption, dependency list, run lineage, and a direct "⇄ Switch Agent" action.

### 6.4 Real Interactive Repository Graph (`ui/src/components/RepositoryGraphVisualizer.jsx`)
- Graph canvas rendering typed nodes: `analysis_unit` (blue), `file` (purple), `register` (amber), `boundary` (red), `module` (green).
- Typed relationships (`contains`, `depends_on`, `maps_to_register`, `crosses_boundary`).
- Filter chips allowing isolation of analysis units, files, or hardware registers.
- Detailed inspector displaying security surface metrics, entry points, assets, and boundaries.

### 6.5 Timeline & Switch Audit Trail
- Filter chips for all event types including `AGENT_SWITCH_COMPLETED`, `AGENT_FAILOVER_COMPLETED`, `MODEL_SWITCH_COMPLETED`, `TOKEN_USAGE_RECORDED`, and `TOKEN_BUDGET_EXHAUSTED`.
- Prominent audit formatting displaying previous agent $\rightarrow$ new agent, trigger actor, and auditable reason.

### 6.6 Settings & Policy Screen (`ui/src/components/SettingsPage.jsx`)
- Added to navigation sidebar under "Control Plane".
- Tabbed management interface:
  - **Agents**: Pool overview, concurrency limits, enable/disable toggles.
  - **Models**: Selection mode (`AUTO`, `MANUAL`, `POLICY`), policy selector (`balanced`, `fast_cost_effective`, `deep_security_reasoning`), model capability matrix table.
  - **Token Budgets**: Default run limits, warning threshold %, auto-stop toggle.
  - **Execution & Scope**: Concurrency limits, retry limits, include/exclude path patterns.
  - **Security & Secrets**: Masked credential indicators (`CONNECTED` / `NOT CONFIGURED`) with strict server-side masking. No cleartext secrets are ever transmitted or stored in the browser.

---

## 7. API Endpoints Matrix (Phase 9.1)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/models` | List all models in ModelRegistry with capabilities and context | Yes |
| `GET` | `/api/models/{model_id}` | Retrieve model capability metadata | Yes |
| `GET` | `/api/agents/{agent_id}/models` | List models compatible with specific agent | Yes |
| `GET` | `/api/tokens` | Authoritative aggregate token summary (actual vs est) | Yes |
| `GET` | `/api/tokens/history` | Paginated token usage records | Yes |
| `GET` | `/api/budgets` | Query scoped token budgets | Yes |
| `PUT` | `/api/budgets` | Update token budget ceiling & thresholds | Yes |
| `POST` | `/api/repository/estimate` | Pre-dispatch repository token estimation | Yes |
| `GET` | `/api/repository/estimate/{id}` | Retrieve stored estimation report | Yes |
| `POST` | `/api/controls/agent-switch` | Execute safe manual agent switch on task | Yes |
| `POST` | `/api/controls/model-switch` | Rebind active model for agent or task | Yes |
| `GET` | `/api/controls/switches` | List audit log of agent and model switches | Yes |
| `GET` | `/api/settings` | Retrieve persistent control plane settings | Yes |
| `PUT` | `/api/settings` | Update settings (with server-side validation) | Yes |
| `GET` | `/api/config` | Retrieve unified system configuration | Yes |

---

## 8. Verification and Test Results

### 8.1 Regression Baseline Verification
The full LLMorch test suite was executed across all phases (Phases 0–9.1):

```text
============================== test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/hackdac/Desktop/intern/LLMorch
collected 288 items

tests/test_bootstrap_readiness.py ...........                             [  3%]
tests/test_elastic_agents.py ..............                              [  8%]
tests/test_global_intelligence.py ...............                        [ 13%]
tests/test_obfuscation.py .............                                  [ 18%]
tests/test_phase1.py .................                                   [ 24%]
tests/test_phase8.py .........................                           [ 32%]
tests/test_phase9_api.py ............................................    [ 48%]
tests/test_phase9_controls.py ...............                            [ 53%]
tests/test_phase9_realtime.py .............                              [ 57%]
tests/test_phase9_1.py ...................                               [ 64%]
tests/test_repository_family.py .................                        [ 70%]
tests/test_sandbox_hardening.py ................                         [ 75%]
tests/test_schemas.py ......                                             [ 77%]
... [All existing test files passed]
======================= 288 passed, 5 warnings in 87.91s =======================
```

### 8.2 Phase 9.1 Unit & Contract Tests (`tests/test_phase9_1.py`)
19 dedicated unit tests covering:
- ModelRegistry auto/manual/policy selection modes
- Model routing capability matching
- Agent switching with checkpoint preservation and run cancellation
- Agent unavailable/disabled rejection
- Authoritative token tracking (actual vs estimated)
- Budget limit transitions (`AVAILABLE` $\rightarrow$ `LOW` $\rightarrow$ `NEAR_LIMIT` $\rightarrow$ `EXHAUSTED`)
- Deterministic budget allocator with reserve allocation
- Pre-dispatch repository token estimation with secrets quarantine
- Automatic failover recording in `AgentSwitchRepository`

**Result**: 19/19 passed.

### 8.3 Phase 9.1 End-to-End Integration Tests (`tests/test_phase9_1_e2e.py`)
4 comprehensive lifecycle tests:
- `test_e2e_repository_estimation_and_budget`: Verifies intake token estimation, exclusion of quarantined secrets, and budget ceiling update.
- `test_e2e_agent_model_resolution`: Verifies ModelRegistry capability querying and agent compatibility.
- `test_e2e_task_execution_token_tracking_and_switching`: Verifies task dispatch, actual token accounting, manual agent switch, run cancellation, child run lineage, and switch audit logging.
- `test_e2e_model_switching_and_settings_persistence`: Verifies dynamic model re-binding, control plane settings update, and safe credential masking.

**Result**: 4/4 passed.

### 8.4 Frontend Production Build
```bash
cd ui && npm run build
```
- Modules transformed: 38
- Bundle built: `dist/index.html` (0.45 kB), `dist/assets/index.css` (16.27 kB), `dist/assets/index.js` (227.02 kB)
- Time: 514 ms
- Status: Clean build, 0 errors, 0 warnings.

---

## 9. Architectural Invariants Preserved

1. **Separation of Concerns**:
   - Orchestrator $\rightarrow$ Agent Registry $\rightarrow$ Task DAG $\rightarrow$ Agent Adapter $\rightarrow$ Model.
   - The browser never mutates state directly; all interactions flow through authenticated FastAPI control plane endpoints.
2. **Authoritative State vs. Client Display**:
   - Browser displays authoritative backend numbers; token estimates are advisory and clearly demarcated from actual consumed tokens.
3. **Lineage Preservation**:
   - Every switch or failover retains the complete lineage chain ($R_1 \rightarrow R_2 \rightarrow R_3$) with valid checkpoints and zero duplicate background worker execution.
4. **Credential Security**:
   - Server-side masked credentials only; cleartext API keys are never exposed in API responses or browser DOM.
5. **Claude Host Safety**:
   - Zero consumption of exhausted Claude CLI host tokens during test execution; adapters utilize AGY, OpenAI Codex, or deterministic Mock harnesses.

---

## 10. Conclusion

LLMorch Phase 9.1 successfully delivers the complete Analyst UI, Investigation Console, dynamic Agent & Model Switching subsystem, Authoritative Token Accounting engine, and Pre-Dispatch Repository Token Estimator. All functional requirements have been implemented and verified with 292 passing automated tests (288 regression + 4 E2E) and a production-ready frontend bundle.
