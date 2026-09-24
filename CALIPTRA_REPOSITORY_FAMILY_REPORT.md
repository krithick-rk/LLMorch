# LLMorch Caliptra Repository Family Support Report

**Date:** 2026-09-24  
**Project:** LLMorch (`/home/hackdac/Desktop/intern/LLMorch`)  
**Architecture Layer:** Repository Family Abstraction & Caliptra Support (Sections 52–59, 76)  
**Status:** IMPLEMENTED  

---

## 1. Architectural Strategy & Design Principles

To support multiple hardware security repository archetypes without polluting the core orchestration plane with hardcoded `if/elif` branching, LLMorch implements the **Repository Family Abstraction** (`repository_intelligence/family.py`).

### Supported Families
1. `OPEN_TITAN_STYLE`: Silicon Root-of-Trust designs using FuseSoC, HJSON register definitions, Bazel/Meson, and C Device Interface Functions (DIF).
2. `CALIPTRA_STYLE`: Open-source silicon RoT designs using Cargo xtask workspaces, SystemRDL register specifications, Rust firmware (ROM, Runtime, Drivers), and Mailbox/SoC integration.
3. `UNKNOWN` / `PARTIALLY_SUPPORTED`: Graceful fallback for generic repositories without breaking the core pipeline.

### Core Invariant Preserved (Section 59)
The core vulnerability research pipeline is **100% family-neutral**:
* `Task`, `Agent`, `Run`, `Evidence`, `Finding`, `Validator`, `Critic`, `Correlator`, `Workspace`, `Sandbox`, and `GlobalIntelligence` are identical across families.
* Only repository intake, register metadata extraction, HW-SW contract detection, and security surface extraction are family-adapted.

---

## 2. Family Detection Mechanism

Family detection evaluates deterministic evidence artifacts rather than mere directory names:

| Family | Detection Signals & Evidence | Confidence Scoring |
|---|---|---|
| **Caliptra-Style** | `Cargo.toml` with `xtask` directory, `*.rdl` SystemRDL files, `caliptra_top.sv` / `mbox*.sv`, Rust ROM/Runtime paths (`rom/`, `runtime/`, `drivers/`) | 0.35 (Cargo xtask) + 0.35 (SystemRDL) + 0.25 (Mailbox RTL) + 0.20 (Rust FW) |
| **OpenTitan-Style** | `*.core` FuseSoC files, `*.hjson` register definitions, Bazel `BUILD` / `BUILD.bazel`, C DIF drivers (`dif_*.h`, `dif_*.c`) | 0.35 (FuseSoC) + 0.35 (HJSON) + 0.20 (Bazel) + 0.20 (DIFs) |

Classification is executed via `detect_repository_family(repo_root: Path)`, returning `(RepositoryFamilyType, RepositoryFamilyAdapter)` with confidence and audit evidence.

---

## 3. Caliptra Architecture Capabilities & Handling

### 3.1. Build Systems & Layout
* **Build System:** Cargo workspace utilizing `xtask` build orchestration (`cargo xtask`).
* **Layout Discovery:**
  - RTL: `src/` (SystemVerilog)
  - Firmware: `rom/`, `runtime/` (Rust bare-metal crates)
  - Registers: `registers/` (SystemRDL)
  - Drivers: `drivers/src/` (Rust driver crates)
  - Verification: `hw-model/`, testbenches

### 3.2. Register Metadata (SystemRDL)
* Caliptra specifies MMIO registers in SystemRDL (`*.rdl`).
* The adapter discovers SystemRDL files, components, and register blocks, normalizing them to uniform register dictionary representations.

### 3.3. Hardware/Software Contracts (`HW_SW_Contract`)
* Caliptra registers map directly to Rust driver structs in `drivers/src/<component>.rs` and RTL modules in `src/<component>.sv`.
* The adapter automatically discovers and establishes `HW_SW_Contract` instances linking the SystemRDL spec (`hjson_ref`), generated Rust driver (`header_ref`), and RTL module (`rtl_module`), verifying synchronization.

### 3.4. Security Surface Construction
* **Assets:**
  - Device Identity Keys (Unique Device Secret - UDS, Composite Device Identifier - CDI) stored in internal Fuse Vault.
  - Attestation PCR Measurement Registers.
* **Trust Boundaries:**
  - SoC-to-Caliptra Mailbox Boundary (`MAILBOX_FIFO`).
  - Caliptra Internal Fuse Vault Boundary (`HARDWARE_ISOLATION`).
* **Attacker Capabilities:** `MALICIOUS_SOC_FIRMWARE`, `PHYSICAL_ACCESS`.
* **Entry Points:**
  - Mailbox Command Register Interface (`MMIO`).
  - JTAG Debug Unlock Port (`bus_interface`).

### 3.5. Validation Backends
* Discoverable backends for Caliptra include:
  - `Cargo_xtask` (Rust unit & integration test runner)
  - `Verilator` (C++ cycle-accurate simulation)
  - `Cocotb` (Python coroutine-driven testbenches)
  - `Emulator` (HW-model simulation)

---

## 4. Verification & Integration Evidence

The Caliptra family adapter was tested against a complete structural Caliptra repository fixture:
* `tests/test_repository_family.py::test_caliptra_family_detection` (PASS)
  - Successfully classified `RepositoryFamilyType.CALIPTRA_STYLE` with confidence >= 0.70.
  - Evidence detected: `cargo_xtask`, `systemrdl_registers`.
* `tests/test_repository_family.py::test_caliptra_normalized_discovery` (PASS)
  - Normalized SystemRDL register components (`mailbox`).
  - Discovered Rust firmware modules (`RUST_FIRMWARE_MODULE`).
  - Established synchronized `HW_SW_Contract` linking `mailbox.rdl`, `mailbox.rs`, and `mailbox.sv`.
  - Constructed comprehensive `SecuritySurface` with SoC-Caliptra Mailbox boundary and Fuse keys.
* `tests/test_repository_family.py::test_opentitan_family_detection` (PASS)
  - OpenTitan compatibility regression verified without breakage.
* `tests/test_repository_family.py::test_family_neutral_core_invariant` (PASS)
  - Confirmed core data contracts (`Task`, `Agent`, `Evidence`, `Finding`, `Validator`) remain 100% agnostic to repository family.

---

## 5. Toolchain Requirements & Host Readiness

Host EDA and software toolchain status for Caliptra workloads:
* **Rust & Cargo:** Installed (`rustc 1.90.0`, `cargo 1.90.0`).
* **Verilator:** Installed (`Verilator 5.024`).
* **Cocotb:** Installed (`cocotb 1.9.2`).
* **Z3 & Boolector:** Installed (`z3-solver 5.1.0.0`, Boolector native binary present).
* **SystemRDL Tooling:** Supported via structural parser and Python SystemRDL compiler tools.
