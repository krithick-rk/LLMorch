# LLMorch Phase 8 Implementation & Architecture Report

## Preflight Hardening → Reproducer Generation → Sandboxed Execution → Independent Validation → Evidence-backed Verdict

```text
Repository: LLMorch
Absolute Path: /home/hackdac/Desktop/intern/LLMorch
Architecture Source: /home/hackdac/Desktop/intern/HWSEC_Multi_Agent_Vulnerability_Research_Master_Report.pdf
Phase: 8 (Reproducers, Hardened Sandbox, Determinism Probing & Independent Validator)
Date: 2026-09-24
```

---

## 1. Executive Summary & Strict Trust Boundary

Phase 8 implements the complete transition from exploratory hypothesis investigation to deterministic, evidence-backed vulnerability reproduction and authoritative validation.

### The Non-Negotiable Trust Model

LLMorch strictly enforces structural security separation between reasoning proposal and empirical verification:

```text
LLM Hypothesis / Reasoning
       ↓ (Untrusted Proposal)
Reproducer Generation Engine (RGE)
       ↓ (Quarantined Package)
Rootless Sandbox (Bubblewrap)
       ↓ (Observable Machine Execution)
Execution Trace
       ↓ (Deterministic Replay Probing)
Independent Validator (Sole Verdict Authority)
       ↓ (Empirical Evidence)
Evidence Plane
       ↓ (Lineage-backed State)
Finding (CONFIRMED / REJECTED / INCONCLUSIVE)
```

### Invariants Maintained
- **LLM claim $\neq$ Evidence:** Natural-language model assertions are quarantined and cannot directly create Evidence records.
- **LLM confidence $\neq$ Verdict:** Model self-assessments have no bearing on finding confirmation.
- **RGE output $\neq$ Verdict:** The Reproducer Generation Engine cannot issue verdicts or declare a reproducer verified.
- **RGE execution $\neq$ Validator Evidence:** Validator conducts its own sandboxed execution and replay runs.
- **Tool / Build / Environment Failure $\neq$ REJECTED:** Infrastructure or toolchain issues result in `INCONCLUSIVE`, never `REJECTED`. Rejection strictly requires positive contradictory evidence (e.g. proof that a security control upholds the invariant).

---

## 2. Pre-Flight Repairs

### Checkpoint 0: Python 3.14 Datetime Cleanup
- **Defect:** Deprecated naive UTC timestamp access via `datetime.utcnow()` triggered thousands of deprecation warnings across Pydantic schemas, adapters, persistence engines, and test fixtures under Python 3.14.
- **Remediation:** All 44 instances across 22 source and test files were replaced with timezone-aware `datetime.now(timezone.utc)` and `default_factory=lambda: datetime.now(timezone.utc)`.
- **Result:** Deprecation warnings dropped from **3,289 warnings to 0 warnings**.
- **Audit Artifact:** [`artifacts/audit/phase8_preflight_datetime.txt`](file:///home/hackdac/Desktop/intern/LLMorch/artifacts/audit/phase8_preflight_datetime.txt).

### Checkpoint 1: Sandbox Hardening & Boundary Security
- **Defect:** Host execution of untrusted reproducer code or generated build scripts poses severe privilege escalation and lateral movement risks.
- **Remediation:** Designed and implemented [`sandbox/runner.py`](file:///home/hackdac/Desktop/intern/LLMorch/sandbox/runner.py) using Linux rootless user namespaces and Bubblewrap (`bwrap 0.11.1`) with process-group supervision fallback.
  - **Read-Only Host Root:** `/usr`, `/lib`, `/bin`, `/etc`, and Python virtualenvs are mounted read-only (`--ro-bind`).
  - **Isolated Writable Workspace:** Only the explicitly allocated run workspace is mounted read-write (`--bind`). Full host filesystem traversal is blocked.
  - **Network Isolation:** Outbound network egress is strictly disabled by default (`--unshare-net`, `--unshare-all`).
  - **Credential & Secret Stripping:** Host credentials (`~/.ssh`, `~/.aws`, `~/.config`, provider API keys, tokens) are completely hidden and stripped from the environment. Pre-flight command compliance checks immediately reject commands referencing protected paths with `POLICY_BLOCKED`.
  - **Resource Bounds & Cancellation:** Timeouts enforce process-group termination (`killpg` SIGTERM followed by SIGKILL), preventing zombie or orphaned processes.
- **Verification:** [`tests/test_sandbox_hardening.py`](file:///home/hackdac/Desktop/intern/LLMorch/tests/test_sandbox_hardening.py) passes 8/8 tests in 2.27s.

---

## 3. Phase 8 Architecture & Component Design

### Architecture Workflow Diagram
```text
Candidate
    │
    ▼
ReproSpec
    │
    ▼
Reproducer Generation Engine
    │
    ├──── existing harness (reused)
    │
    └──── generated harness
              │
              ▼
         Quarantine
              │
              ▼
          Minimizer
              │
              ▼
      Reproducer Package (Sealed Manifest)
              │
              ▼
      Integrity Verification (Canonical SHA-256)
              │
              ▼
       Rootless Sandbox (Bubblewrap)
              │
              ▼
       Execution Trace (Machine-Generated)
              │
              ▼
           Replay (Multi-Pass Determinism Probing)
              │
              ▼
     Independent Validator (Sole Verdict Authority)
        │       │       │
        ▼       ▼       ▼
   CONFIRMED REJECTED INCONCLUSIVE
        │       │       │
        └───────┴───────┘
                ▼
          Evidence Plane
                │
                ▼
             Finding
```

### Component Breakdown

1. **Candidate Model (`schemas/candidate.py`):**
   - Encapsulates an investigated security hypothesis without conferring confirmed status.
   - Captures `candidate_id`, `analysis_unit_id`, `hypothesis_id`, `security_property`, `attack_surface`, `attack_path`, `expected_behavior`, `suspected_behavior`, `source_references`, `tool_observations`, `memory_references`.

2. **ReproSpec Model (`schemas/reprospec.py`):**
   - Specification blueprint defining reproduction preconditions, entry point, trigger sequence, expected failure signal, toolchain requirements, build procedure, and requested replay count.

3. **Reproducer State Machine (`schemas/reproducer.py`):**
   - States: `PROPOSED` $\rightarrow$ `GENERATING` $\rightarrow$ `GENERATED` $\rightarrow$ `BUILDING` $\rightarrow$ `BUILT` $\rightarrow$ `MINIMIZING` $\rightarrow$ `MINIMIZED` $\rightarrow$ `SANDBOXED` $\rightarrow$ `READY_FOR_VALIDATION` $\rightarrow$ `VALIDATING` $\rightarrow$ `CONFIRMED` / `REJECTED` / `INCONCLUSIVE`.
   - Error states: `GENERATION_FAILED`, `SANDBOX_FAILED`, `VALIDATION_FAILED`, `INVALIDATED`.

4. **Reproducer Generation Engine (`reproducers/generator.py`):**
   - Scans repository for existing test suites and harnesses before synthesizing new code.
   - Quarantines all generated harnesses in a designated quarantine workspace.
   - Computes canonical manifest SHA-256 excluding the manifest signature itself.
   - Strictly forbidden from issuing verdicts or writing to the Evidence Plane.

5. **Minimization Engine (`reproducers/minimizer.py`):**
   - Reduces code, inputs, and stimuli (Python, C/C++, stimulus) while preserving failure triggers.
   - **Baseline Retention Guarantee:** If minimized artifact $B$ fails validator reproduction, the validator retains original artifact $A$. Minimized claims are unverified until independently executed.

6. **Sandbox Runner (`sandbox/runner.py`):**
   - Executes untrusted reproducers inside Bubblewrap jails with sanitized environment.
   - Generates machine-certified `ExecutionTrace` with SHA-256 hashes of stdout/stderr, wall time, resource metrics, exit code, and environment fingerprint.

7. **Independent Validator Engine (`validator/service.py`):**
   - **Integrity Check:** Validates manifest canonical hash and artifact hashes. Modified files trigger `REPRODUCER_INVALIDATED` $\rightarrow$ `INCONCLUSIVE`.
   - **Tool Availability:** Missing tools trigger `INCONCLUSIVE` (never `REJECTED`).
   - **Controlled Build:** Build failures trigger `INCONCLUSIVE` (never `REJECTED`).
   - **Primary Execution:** Evaluates machine-generated trace against declared failure signal.
   - **Multi-Pass Determinism Probing:** Executes $N$ replay runs; classifies as `DETERMINISTIC`, `FLAKY`, `VARIABLE`, `NON_REPRODUCING`.
   - **Evidence Plane Integration:** Writes verified `Evidence` records linking sandbox execution ID and reproducer ID.

---

## 4. Verification & Control Testing

### 1. Positive Control (`test_positive_control_confirmed`)
- **Setup:** Target script with reproducible security assertion violation (`HARDWARE_SECURITY_VIOLATION`).
- **Result:** Executed in sandbox $\rightarrow$ primary run produced failure $\rightarrow$ replays replicated failure deterministically $\rightarrow$ Validator emitted `CONFIRMED` with confidence `1.0`.

### 2. Hard Negative Control (`test_hard_negative_rejected`)
- **Setup:** Hypothesis claims out-of-bounds access defect, but code contains valid bounds check (`check_access`). Code executes cleanly with exit code 0 and passes all assertions.
- **Result:** Executed across replays $\rightarrow$ all replays cleanly succeeded $\rightarrow$ Validator emitted `REJECTED` with positive contradictory evidence proving the security control held.

### 3. Inconclusive Controls
- **Missing Tool (`test_tool_unavailable_inconclusive`):** Required tool `tool_that_does_not_exist_xyz123` missing $\rightarrow$ Validator emitted `INCONCLUSIVE`.
- **Build Failure (`test_environment_failure_inconclusive`):** Build command returned exit code 1 $\rightarrow$ Validator emitted `INCONCLUSIVE`.
- **Policy Blocked (`test_sandbox_failure_inconclusive`):** Script attempted host secret access $\rightarrow$ blocked before execution $\rightarrow$ Validator emitted `INCONCLUSIVE`.
- **Flaky Behavior (`test_variable_replay`):** Reproducer exhibited variable exit codes across replays $\rightarrow$ classified `FLAKY` $\rightarrow$ Validator emitted `INCONCLUSIVE`.

### 4. Real RTL Simulation Control (`test_rtl_simulation_validation_control`)
- **Tooling:** Real SystemVerilog syntax & lint validation via `slang 11.0` (installed on host).
- **Result:** Successfully validated SystemVerilog RTL counter bug fixture through sandboxed execution trace.

### 5. Real Formal Control (`test_formal_z3_validation_control`)
- **Tooling:** Real formal solver verification via `z3 5.1.0` (installed on host).
- **Result:** SMT solver evaluated key invariant, discovered counterexample model, exited with code 1, and Validator confirmed property violation backed by machine trace.

---

## 5. Integration with Phases 0–7

1. **Repository Family Integration (OpenTitan & Caliptra):**
   - Consumes `OpenTitanFamilyAdapter` and `CaliptraFamilyAdapter` from Phase 7 to resolve IP blocks (`aes`, `hmac`), register layouts (HJSON/SystemRDL), and hardware-software contracts.
2. **Phase 6 Cross-Project Memory Integration:**
   - Reproducer generator queries `MemoryService.retrieve()` to guide reproducer strategy from historical vulnerability patterns without leaking private source.
3. **Phase 4–5 Agent Elasticity & Failover:**
   - Supports 1, 2, 3, or 4 agents in pool.
   - Independent agents execute in isolated worktrees with separate manifests and quarantine directories.
   - Failover engine cleanly reassigns tasks upon agent failure without corrupting candidate data.

---

## 6. CLI Commands

Phase 8 adds complete CLI commands under `python3 -m llmorch`:
- `python3 -m llmorch repro list`: Lists all recorded reproducer packages with state and domain.
- `python3 -m llmorch repro inspect <reproducer_id>`: Dumps sanitized reproducer manifest.
- `python3 -m llmorch repro run <reproducer_id>`: Executes reproducer in hardened sandbox.
- `python3 -m llmorch validate <reproducer_id>`: Submits reproducer to Independent Validator and outputs authoritative verdict.
- `python3 -m llmorch validation inspect <validation_id>`: Dumps complete validation verdict with determinism and evidence IDs.

---

## 7. Known Limitations

1. **Host-Specific Podman cgroups:** On Linux systems where rootless Podman lacks systemd dbus user delegation, LLMorch automatically utilizes unprivileged Bubblewrap (`bwrap`) user namespaces.
2. **Formal Engine Timeouts:** Large formal properties requiring deeper bounds must configure explicit timeout and solver budgets in `SandboxPolicy` to prevent solver hangs.
