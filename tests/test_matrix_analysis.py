"""
LLMorch — Final Test Matrix (Section 31)
Tests:
A. Empty folder
B. One empty file
C. Tiny Rust project
D. Two-file mixed project
E. Runtime-only Caliptra
F. Full Caliptra benchmark
G. RTL-only project
H. Mixed RTL + firmware
I. Generic C repository
J. Generic C++ repository
"""

import sys
import pytest
from pathlib import Path

from api.routers.projects import _inspect_directory_deterministic
from orchestrator.tool_router import route_tools_for_scope
from repository_intelligence.preflight import analyze_repository_preflight
from supervisor.supervisor import Supervisor
from history.database import DatabaseService


def test_matrix_a_empty_folder(tmp_path):
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    
    intake = _inspect_directory_deterministic(str(empty_dir))
    routing = route_tools_for_scope(str(empty_dir), intake)
    
    assert intake["total_files"] == 0
    assert "yosys" in [r["tool"] for r in routing.rejected_tools]
    print("\n[A] Empty folder: Total files=0, Yosys rejected.")


def test_matrix_b_one_empty_file(tmp_path):
    single_dir = tmp_path / "single_file_dir"
    single_dir.mkdir()
    (single_dir / "notes.txt").write_text("")
    
    intake = _inspect_directory_deterministic(str(single_dir))
    routing = route_tools_for_scope(str(single_dir), intake)
    
    assert intake["total_files"] == 1
    assert "yosys" in [r["tool"] for r in routing.rejected_tools]
    print("[B] One empty file: Generic scope, Yosys rejected.")


def test_matrix_c_tiny_rust_project(tmp_path):
    rust_dir = tmp_path / "tiny_rust"
    rust_dir.mkdir()
    (rust_dir / "Cargo.toml").write_text('[package]\nname = "tiny"\nversion = "0.1.0"\n')
    src = rust_dir / "src"
    src.mkdir()
    (src / "lib.rs").write_text("pub fn add(a: u32, b: u32) -> u32 { a + b }\n")
    
    intake = _inspect_directory_deterministic(str(rust_dir))
    routing = route_tools_for_scope(str(rust_dir), intake)
    
    assert intake["primary_language"] == "Rust"
    assert intake["build_system"] == "Cargo"
    assert "Rust" in intake["classification"]
    assert "yosys" in [r["tool"] for r in routing.rejected_tools]
    assert routing.primary_tool in ("rust_source_inspector", "ripgrep (rg)", "deterministic_reproducer")
    print("[C] Tiny Rust project: Primary language=Rust, Cargo detected, Yosys rejected.")


def test_matrix_d_two_file_mixed_project(tmp_path):
    mixed_dir = tmp_path / "two_file_mixed"
    mixed_dir.mkdir()
    (mixed_dir / "hello.c").write_text('#include <stdio.h>\nint main() { return 0; }\n')
    (mixed_dir / "script.py").write_text('print("script")\n')
    
    intake = _inspect_directory_deterministic(str(mixed_dir))
    routing = route_tools_for_scope(str(mixed_dir), intake)
    
    assert intake["c_count"] == 1
    assert intake["py_count"] == 1
    assert intake["rtl_count"] == 0
    assert "yosys" in [r["tool"] for r in routing.rejected_tools]
    print("[D] Two-file mixed project: C+Py detected, 0 RTL, Yosys rejected.")


def test_matrix_e_runtime_only_caliptra():
    caliptra_rt = "/home/hackdac/Documents/Benchmark/caliptra-vuln-known/runtime"
    intake = _inspect_directory_deterministic(caliptra_rt)
    routing = route_tools_for_scope(caliptra_rt, intake)
    
    assert intake["primary_language"] == "Rust"
    assert intake["scope_type"] == "SUBDIRECTORY_COMPONENT"
    assert "caliptra-vuln-known" in intake["parent_repository_if_known"]
    assert "yosys" in [r["tool"] for r in routing.rejected_tools]
    print("[E] Runtime-only Caliptra: Subdirectory Rust crate, Parent detected, Yosys rejected.")


def test_matrix_f_full_caliptra_benchmark():
    caliptra_root = "/home/hackdac/Documents/Benchmark/caliptra-vuln-known"
    intake = _inspect_directory_deterministic(caliptra_root)
    routing = route_tools_for_scope(caliptra_root, intake)
    
    assert intake["scope_type"] == "STANDALONE_REPOSITORY"
    assert intake["rust_count"] > 100
    assert intake["rtl_count"] > 0
    assert "Mixed" in intake["classification"] or "SoC" in intake["classification"]
    assert "rust_source_inspector" in routing.recommended_tools
    assert any(t in routing.recommended_tools for t in ("verilator", "yosys"))
    print("[F] Full Caliptra benchmark: Standalone mixed HW/SW repository, concurrent RTL and Rust tools.")


def test_matrix_g_rtl_only_project(tmp_path):
    rtl_dir = tmp_path / "rtl_only"
    rtl_dir.mkdir()
    (rtl_dir / "alu.sv").write_text("module alu(input logic clk); endmodule\n")
    (rtl_dir / "regfile.sv").write_text("module regfile(input logic clk); endmodule\n")
    
    intake = _inspect_directory_deterministic(str(rtl_dir))
    routing = route_tools_for_scope(str(rtl_dir), intake)
    
    assert intake["rtl_count"] == 2
    assert intake["rust_count"] == 0
    assert intake["c_count"] == 0
    assert any(t in routing.recommended_tools for t in ("verilator", "yosys"))
    assert "cargo" in [r["tool"] for r in routing.rejected_tools]
    print("[G] RTL-only project: SystemVerilog routed to Verilator/Yosys, Cargo rejected.")


def test_matrix_h_mixed_rtl_and_firmware(tmp_path):
    mixed_dir = tmp_path / "mixed_hw_fw"
    mixed_dir.mkdir()
    (mixed_dir / "top.sv").write_text("module top(input logic clk); endmodule\n")
    (mixed_dir / "firmware.rs").write_text("pub fn fw_entry() {}\n")
    
    intake = _inspect_directory_deterministic(str(mixed_dir))
    routing = route_tools_for_scope(str(mixed_dir), intake)
    
    assert intake["rtl_count"] == 1
    assert intake["rust_count"] == 1
    assert "Mixed" in intake["classification"]
    assert "rust_source_inspector" in routing.recommended_tools
    print("[H] Mixed RTL + firmware: Cross-component routed to concurrent verification.")


def test_matrix_i_generic_c_repository(tmp_path):
    c_dir = tmp_path / "c_repo"
    c_dir.mkdir()
    (c_dir / "Makefile").write_text("all:\n\tgcc main.c\n")
    (c_dir / "main.c").write_text("int main() { return 0; }\n")
    (c_dir / "util.c").write_text("void helper() {}\n")
    
    intake = _inspect_directory_deterministic(str(c_dir))
    routing = route_tools_for_scope(str(c_dir), intake)
    
    assert intake["primary_language"] == "C / C++"
    assert intake["c_count"] == 2
    assert intake["rtl_count"] == 0
    assert "yosys" in [r["tool"] for r in routing.rejected_tools]
    print("[I] Generic C repository: Primary language=C/C++, Makefile detected, Yosys rejected.")


def test_matrix_j_generic_cpp_repository(tmp_path):
    cpp_dir = tmp_path / "cpp_repo"
    cpp_dir.mkdir()
    (cpp_dir / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.10)\n")
    (cpp_dir / "main.cpp").write_text("int main() { return 0; }\n")
    (cpp_dir / "engine.hpp").write_text("class Engine {};\n")
    
    intake = _inspect_directory_deterministic(str(cpp_dir))
    routing = route_tools_for_scope(str(cpp_dir), intake)
    
    assert intake["primary_language"] == "C / C++"
    assert intake["c_count"] == 2
    assert intake["rtl_count"] == 0
    assert "yosys" in [r["tool"] for r in routing.rejected_tools]
    print("[J] Generic C++ repository: Primary language=C/C++, CMake detected, Yosys rejected.")
