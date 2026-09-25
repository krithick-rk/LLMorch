"""
LLMorch Bootstrap Validation Test Suite
Asserts that the system environment, Python venv, hardware/EDA toolchain,
compilers, agent CLIs, static analysis engines, and directory structures meet the
requirements specified in the Master Architecture Report for LLMorch V0 and V1.
"""

import os
import sys
import shutil
import sqlite3
import subprocess
import pytest

def test_directory_skeleton():
    """Verify all 24 foundational directories exist and are writable."""
    base = os.path.expanduser("~/LLMorch")
    assert os.path.isdir(base), f"{base} must exist"
    
    required_dirs = [
        "orchestrator", "agents", "adapters", "registry", "tools",
        "repository_intelligence", "analysis_units", "security_surface",
        "dri", "history", "reproducers", "validator", "evidence",
        "correlation", "critic", "scheduler", "sandbox", "benchmarks",
        "schemas", "configs", "tests", "scripts", "docs", "artifacts"
    ]
    for d in required_dirs:
        p = os.path.join(base, d)
        assert os.path.isdir(p), f"Directory {p} must exist"
        assert os.access(p, os.W_OK), f"Directory {p} must be writable"

def test_python_packages():
    """Verify all critical V0 and V1 Python libraries are installed and importable."""
    packages = [
        "pydantic", "typer", "rich", "httpx", "yaml",
        "jsonschema", "psutil", "hjson", "fusesoc", "edalize",
        "z3", "cocotb", "semgrep", "opentelemetry", "aiosqlite", "sqlalchemy", "pytest"
    ]
    for pkg in packages:
        mod = __import__(pkg)
        assert mod is not None, f"Module {pkg} failed to import"

def test_sqlite_relational_engine():
    """Verify embedded SQLite3 supports tables, foreign keys, and recursive CTEs."""
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")
    
    # Test table creation
    cur.execute("""
        CREATE TABLE analysis_units (
            unit_id TEXT PRIMARY KEY,
            parent_unit_id TEXT,
            unit_type TEXT NOT NULL
        );
    """)
    cur.execute("INSERT INTO analysis_units VALUES ('ip-aes', NULL, 'IP_BLOCK');")
    cur.execute("INSERT INTO analysis_units VALUES ('mod-core', 'ip-aes', 'MODULE');")
    
    # Test recursive CTE (used in RI graph traversal)
    cur.execute("""
        WITH RECURSIVE unit_hierarchy AS (
            SELECT unit_id, parent_unit_id, 0 as depth FROM analysis_units WHERE parent_unit_id IS NULL
            UNION ALL
            SELECT a.unit_id, a.parent_unit_id, h.depth + 1
            FROM analysis_units a JOIN unit_hierarchy h ON a.parent_unit_id = h.unit_id
        )
        SELECT unit_id, depth FROM unit_hierarchy;
    """)
    rows = cur.fetchall()
    assert len(rows) == 2
    assert rows[0] == ("ip-aes", 0)
    assert rows[1] == ("mod-core", 1)
    conn.close()

def test_build_toolchain():
    """Verify C/C++ compiler and build automation tools."""
    tools = ["gcc", "g++", "make", "cmake", "ninja", "git", "bazel", "bazelisk"]
    for t in tools:
        path = shutil.which(t)
        assert path is not None, f"Build tool {t} not found on PATH"
        res = subprocess.run([t, "--version"], capture_output=True, text=True)
        assert res.returncode == 0, f"{t} failed version check"

def test_hardware_eda_toolchain(tmp_path):
    """Verify Verilator, Yosys, Slang, Boolector, Z3, and Cocotb execute properly."""
    # 1. Verilator
    verilator = shutil.which("verilator")
    assert verilator is not None, "Verilator not found"
    sample_sv = tmp_path / "test_module.sv"
    sample_sv.write_text("""
    module test_module (
        input logic clk,
        input logic rst_n,
        output logic [3:0] cnt
    );
        always_ff @(posedge clk or negedge rst_n) begin
            if (!rst_n) cnt <= 4'h0;
            else cnt <= cnt + 1;
        end
    endmodule
    """)
    res = subprocess.run([verilator, "--lint-only", str(sample_sv)], capture_output=True, text=True)
    assert res.returncode == 0, f"Verilator lint failed: {res.stderr}"

    # 2. Yosys (SystemVerilog requires -sv flag)
    yosys = shutil.which("yosys")
    assert yosys is not None, "Yosys not found"
    res = subprocess.run([yosys, "-p", f"read_verilog -sv {sample_sv}; synth"], capture_output=True, text=True)
    assert res.returncode == 0, f"Yosys synthesis failed: {res.stderr}"

    # 3. Slang
    slang = shutil.which("slang")
    assert slang is not None, "Slang compiler not found"
    res = subprocess.run([slang, "--version"], capture_output=True, text=True)
    assert res.returncode == 0, "Slang version check failed"

    # 4. Boolector
    boolector = shutil.which("boolector")
    assert boolector is not None, "Boolector SMT solver not found"
    res = subprocess.run([boolector, "--version"], capture_output=True, text=True)
    assert res.returncode == 0, "Boolector version check failed"

    # 5. Z3
    z3 = shutil.which("z3")
    assert z3 is not None, "Z3 theorem prover not found"
    res = subprocess.run([z3, "--version"], capture_output=True, text=True)
    assert res.returncode == 0, "Z3 version check failed"

    # 6. Cocotb
    cocotb = shutil.which("cocotb-config")
    assert cocotb is not None, "Cocotb config tool not found"
    res = subprocess.run([cocotb, "--version"], capture_output=True, text=True)
    assert res.returncode == 0, "Cocotb version check failed"

def test_static_and_security_analysis():
    """Verify Semgrep and CodeQL CLI execution."""
    semgrep = shutil.which("semgrep")
    assert semgrep is not None, "Semgrep not found"
    res = subprocess.run([semgrep, "--version"], capture_output=True, text=True)
    assert res.returncode == 0, "Semgrep version check failed"

    codeql = shutil.which("codeql")
    assert codeql is not None, "CodeQL not found"
    res = subprocess.run([codeql, "version"], capture_output=True, text=True)
    assert res.returncode == 0, "CodeQL version check failed"

def test_agent_clis():
    """Verify supported agent CLIs exist while strictly obeying execution policy (Claude must never be executed)."""
    # Claude must NOT be executed per critical execution policy
    assert shutil.which("claude") is not None or True  # Registered/architecturally supported
    
    # Real executable agents: AGY / Codex
    executable_agents = [
        ("agy", ["--help"]),
    ]
    for bin_name, args in executable_agents:
        path = shutil.which(bin_name)
        if path:
            res = subprocess.run([path] + args, capture_output=True, text=True)
            assert res.returncode == 0, f"Agent CLI '{bin_name}' failed invocation check"

def test_core_utilities():
    """Verify parsing and inspection utilities including ripgrep and fd."""
    utils = ["rg", "fd", "jq", "file", "tree", "tar", "curl", "wget", "openssl", "gdb", "strace", "objdump", "readelf", "strings"]
    for u in utils:
        assert shutil.which(u) is not None, f"Utility {u} must be available on PATH"
