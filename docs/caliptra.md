# Caliptra Repository Architecture Support

Caliptra is an open-source Silicon Root of Trust for Measurement (RTM) specified by the Open Compute Project (OCP) and CHIPS Alliance.

## Caliptra Architecture Model in LLMorch
* **Build System:** Cargo workspace with `xtask` (`cargo xtask`).
* **Registers:** SystemRDL (`*.rdl`) files mapped to Rust driver crates (`drivers/src/*.rs`) and SystemVerilog RTL (`src/*.sv`).
* **Firmware:** Bare-metal Rust ROM (`rom/`) and Runtime firmware (`runtime/`).
* **Security Boundaries:**
  * SoC-to-Caliptra Mailbox Interface (`MAILBOX_FIFO`).
  * Internal Fuse Vault Isolation (`HARDWARE_ISOLATION`).
* **Assets:**
  * Unique Device Secret (UDS) / Composite Device Identifier (CDI).
  * Attestation Platform Configuration Registers (PCRs).
* **Validation Backends:** Cargo xtask, Cocotb, Verilator, HW-model emulator.
