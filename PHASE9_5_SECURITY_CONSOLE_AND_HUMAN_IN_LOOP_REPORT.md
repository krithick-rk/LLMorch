# LLMorch Phase 9.5: Security Research Operations Console & Human-in-the-Loop Decision Architecture Report

## Executive Summary

Phase 9.5 elevates **LLMorch** from an autonomous execution prototype into an enterprise-grade **Security Research Operations Console**. It delivers deterministic orchestration, authoritative active security timer semantics, truthful agent runtime availability, generic and empty-repository intelligence, transparent right-side operational streams, bottom human-in-the-loop decision inbox, stall loop protection, attempt lineage preservation, persistent URL routing, and a restrained SIEM/SOC dark theme.

---

## Critical Execution Policy

- **Executable Agents:** `Antigravity / AGY` and `Codex CLI` are fully operational and executable.
- **Claude Code Policy:** Registered in Model and Agent Registry (`registered=True`), architecturally supported, and visible in UI console (`Execution: DISABLED BY POLICY`). Real Claude Code CLI executable is never invoked at runtime or during test execution.

---

## Architectural Breakdown & Verification

### 1. Repository Lifecycle & Generic Intake
- Initial repository analysis is decoupled into a dedicated intake stage (`REPOSITORY_ANALYSIS` → `WAITING_FOR_ANALYST`) before security attack workflows begin.
- Unknown repository families utilize a generic fallback scanner that deterministically classifies languages, build systems, security surfaces, and recommended tools.

### 2. Empty-File & Tiny-Repository Correctness
- Empty repositories (e.g. `empty.c` with 0 bytes) yield exactly 0 LLM source tokens, 0 primary source AnalysisUnits, and trigger an automated Analyst Question ("The repository contains an empty file. What should I do?").
- Token estimation scales proportionally to eligible source bytes without arbitrary minimum floors.

### 3. Truthful Agent Runtime & Terminal Guidance
- Truthful detection of CLI binary installation, version, execution readiness, and connectivity status.
- Zero-agent and single-agent states are handled gracefully: 1 executable agent is sufficient.
- `[Open Local Terminal]` endpoint and UI controls provide non-credential-leaking local shell commands for user authentication and account switching.

### 4. Authoritative Active Security Timer
- Active security timer is 0 during intake and waiting stages.
- The timer starts ONLY upon analyst clicking `[START SECURITY ANALYSIS]`.
- Freezes on `PAUSED`, `STOPPED`, `COMPLETED`, `FAILED`.
- Resets to 0 for every new run session.

### 5. Right-Side Agent Activity Stream & Bottom Decision Inbox
- **Agent Activity Stream:** Placed on the **RIGHT** side of the main workflow canvas, rendering transparent operational records (tool invocations, exit codes, observations, hypotheses, evidence links) while strictly omitting private chain-of-thought.
- **Analyst Decision Inbox:** Placed at the **BOTTOM** of the workflow console, rendering first-class `AnalystQuestion` entities with options, custom guidance input, dismiss/submit actions, and stall warnings.

### 6. Stall Protection & Attempt Lineage
- `StallDetector` monitors repetitive tool invocations, commands, and non-progressing loops, automatically pausing execution and filing an analyst decision item.
- Analyst instructions spawn immutable `TaskAttempt` entities (Attempt 2+) while preserving full predecessor lineage, tool executions, and evidence references.

### 7. Persistent Entity URLs & New-Tab Support
- Authoritative backend state hydration and browser URL synchronization for:
  - `/run/{run_id}`
  - `/repository/{repository_id}`
  - `/agent/{agent_id}`
  - `/task/{task_id}`
  - `/finding/{finding_id}`
  - `/evidence/{evidence_id}`
  - `/tool/{tool_id}`
  - `/question/{question_id}`
  - `/attempt/{attempt_id}`

---

## Verification & Compliance Matrix

| Feature | Backend | UI | Automated Tests | Manual E2E |
| :--- | :---: | :---: | :---: | :---: |
| **Repository Intake Lifecycle** | Authoritative | Stepper Review UI | PASS (`test_phase9_5.py`) | PASS |
| **Empty File / Zero-Token Handling** | Filtered (0 units) | Clear explanation & Question | PASS (`test_phase9_5.py`) | PASS |
| **Generic Unknown Repo Intelligence** | Deterministic fallback | Generic capability report | PASS (`test_phase9_5.py`) | PASS |
| **Agent Runtime Status & Terminal** | Truthful inspection | Status badge & Terminal guidance | PASS (`test_phase9_5.py`) | PASS |
| **Claude Execution Policy Block** | Enforced | Disabled by policy | PASS (`test_phase9_5.py`) | PASS |
| **Authoritative Security Timer** | State-driven duration | Elapsed header ticker | PASS (`test_phase9_5.py`) | PASS |
| **Right-Side Agent Activity Stream** | Realtime stream | Right panel layout | PASS (`test_phase9_3.py`) | PASS |
| **Bottom Analyst Decision Inbox** | Question lifecycle CRUD | Interactive bottom card | PASS (`test_phase9_5.py`) | PASS |
| **Stall Protection Guard** | Loop detector | Stalled state & Question | PASS (`test_phase9_5.py`) | PASS |
| **Attempt Lineage & Instructions** | Immutable attempts | Workroom attempt switcher | PASS (`test_phase9_5.py`) | PASS |
| **Persistent URLs & Refresh Sync** | REST endpoints | Browser URL popstate sync | PASS (`test_phase9_4.py`) | PASS |
| **PoC Sandbox & Validator Authority** | Isolated execution | Dossier validation badge | PASS (`test_phase9_1/9.3`) | PASS |

---

## Build & Test Status

- **Frontend Bundle Build:** `npm run build` (Vite 4.5.14) compiled in **942ms** with 0 errors.
- **Backend Test Suite:** Pytest suites passing across bootstrap readiness, phase 9.1, 9.2, 9.3, 9.4, and 9.5 suites.
