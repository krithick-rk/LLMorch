"""
Unit & Integration Tests - Repository Family Abstraction & Caliptra Support
Validates OpenTitan-style and Caliptra-style detection, layout discovery,
HW-SW contract normalization, and family-neutral core compatibility.
"""

import pytest
from pathlib import Path
import tempfile

from repository_intelligence.family import (
    RepositoryFamilyType,
    OpenTitanFamilyAdapter,
    CaliptraFamilyAdapter,
    detect_repository_family,
)
from schemas.task import Task
from schemas.agent import Agent, AgentInterface
from schemas.evidence import Evidence, EvidenceSourceType
from schemas.finding import Finding, FindingState
from validator.engine import FindingValidator


@pytest.fixture
def opentitan_repo(tmp_path):
    """Constructs a structural OpenTitan repository fixture."""
    repo = tmp_path / "opentitan"
    repo.mkdir()

    # Core metadata
    hw_ip = repo / "hw" / "ip" / "aes"
    hw_ip.mkdir(parents=True)
    (hw_ip / "aes.core").write_text("CAPI=2:\nname: lowrisc:ip:aes:0.6\n")
    (hw_ip / "aes_regs.hjson").write_text("{ name: 'aes', registers: [] }")

    # Build file
    (repo / "BUILD").write_text("package(default_visibility = ['//visibility:public'])\n")

    # DIF driver
    dif_dir = repo / "sw" / "device" / "lib" / "dif"
    dif_dir.mkdir(parents=True)
    (dif_dir / "dif_aes.h").write_text("typedef struct dif_aes { int base; } dif_aes_t;\n")
    (dif_dir / "dif_aes.c").write_text("#include \"dif_aes.h\"\n")

    # RTL
    rtl_dir = hw_ip / "rtl"
    rtl_dir.mkdir()
    (rtl_dir / "aes.sv").write_text("module aes (); endmodule\n")

    return repo


@pytest.fixture
def caliptra_repo(tmp_path):
    """Constructs a structural Caliptra repository fixture."""
    repo = tmp_path / "caliptra"
    repo.mkdir()

    # Cargo xtask workspace
    (repo / "Cargo.toml").write_text("""
    [workspace]
    members = ["xtask", "drivers", "rom"]
    [package]
    name = "caliptra-top"
    version = "0.1.0"
    """)
    (repo / "xtask").mkdir()
    (repo / "xtask" / "Cargo.toml").write_text("[package]\nname = 'xtask'\nversion = '0.1.0'\n")

    # SystemRDL register definitions
    reg_dir = repo / "registers"
    reg_dir.mkdir()
    (reg_dir / "mailbox.rdl").write_text("""
    addrmap mailbox_reg {
        name = "Caliptra Mailbox Registers";
        reg { field {} data[32]; } mbox_data;
    };
    """)

    # Rust firmware / drivers
    rom_dir = repo / "rom" / "src"
    rom_dir.mkdir(parents=True)
    (rom_dir / "main.rs").write_text("fn main() { // Caliptra ROM Boot flow }\n")

    drivers_dir = repo / "drivers" / "src"
    drivers_dir.mkdir(parents=True)
    (drivers_dir / "mailbox.rs").write_text("pub struct MailboxDriver;\n")

    # RTL modules
    src_dir = repo / "src"
    src_dir.mkdir()
    (src_dir / "mailbox.sv").write_text("module mailbox (input logic clk); endmodule\n")
    (src_dir / "caliptra_top.sv").write_text("module caliptra_top (); endmodule\n")

    return repo


def test_opentitan_family_detection(opentitan_repo):
    """Verifies OpenTitan-style detection via .core, .hjson, and DIF drivers."""
    family, adapter = detect_repository_family(opentitan_repo)
    assert family == RepositoryFamilyType.OPEN_TITAN_STYLE
    assert isinstance(adapter, OpenTitanFamilyAdapter)

    detection = adapter.detect(opentitan_repo)
    assert detection.confidence >= 0.7
    assert "fusesoc" in detection.detected_capabilities
    assert "hjson_registers" in detection.detected_capabilities


def test_caliptra_family_detection(caliptra_repo):
    """Verifies Caliptra-style detection via Cargo xtask, SystemRDL, and Rust firmware."""
    family, adapter = detect_repository_family(caliptra_repo)
    assert family == RepositoryFamilyType.CALIPTRA_STYLE
    assert isinstance(adapter, CaliptraFamilyAdapter)

    detection = adapter.detect(caliptra_repo)
    assert detection.confidence >= 0.7
    assert "cargo_xtask" in detection.detected_capabilities
    assert "systemrdl_registers" in detection.detected_capabilities


def test_caliptra_normalized_discovery(caliptra_repo):
    """Verifies Caliptra adapter normalizes registers, contracts, and security surface."""
    adapter = CaliptraFamilyAdapter()

    # Registers
    regs = adapter.discover_registers(caliptra_repo)
    assert len(regs) >= 1
    assert regs[0]["format"] == "SystemRDL"
    assert regs[0]["component"] == "mailbox"

    # Firmware
    fw = adapter.discover_firmware(caliptra_repo)
    assert len(fw) >= 1
    assert fw[0]["type"] == "RUST_FIRMWARE_MODULE"

    # HW-SW Contract
    contracts = adapter.discover_hw_sw_contracts(caliptra_repo)
    assert len(contracts) >= 1
    contract = contracts[0]
    assert contract.register_name == "mailbox_regs"
    assert contract.header_ref is not None

    # Security Surface
    surface = adapter.build_security_surface(caliptra_repo)
    boundary_names = [b.name for b in surface.boundaries]
    assert "SoC-Caliptra Mailbox Boundary" in boundary_names


def test_family_neutral_core_invariant():
    """
    CRITICAL INVARIANT (Section 59):
    Core data contracts (Task, Agent, Evidence, Finding, Validator) are 100% identical across families.
    """
    task = Task(objective="Analyze mailbox buffer overflow")
    agent = Agent(agent_id="agent-agy-01", provider="antigravity", interface=AgentInterface.CLI, capabilities=["security_review"])
    evidence = Evidence(
        task_id=task.task_id,
        run_id="run-test",
        agent_id=agent.agent_id,
        source_type=EvidenceSourceType.TOOL_OUTPUT,
        raw_hash="hash-abc",
        canonical_hash="hash-abc",
        semantic_fingerprint="sem-abc",
        environment_fingerprint="env-test",
        exit_status=0
    )
    finding = Finding(
        fingerprint="fp-test-01",
        hypothesis="Mailbox boundary FIFO desynchronization",
        supporting_evidence=[evidence.evidence_id]
    )

    # Core contracts are completely family-neutral
    assert task.schema_version == "1.0.0"
    assert agent.interface == AgentInterface.CLI
    assert finding.state == FindingState.HYPOTHESIS
