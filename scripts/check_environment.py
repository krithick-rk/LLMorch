#!/usr/bin/env python3
"""
LLMorch Environment Verification and Health Check Script
Performs a comprehensive audit of the host system, development toolchains,
hardware/EDA tools, security tools, container runtimes, database layers,
and terminal agent CLIs based on the LLMorch Master Architecture Report.
"""

import os
import sys
import json
import shutil
import platform
import subprocess
from typing import Dict, Any, List, Optional

def run_cmd(cmd: List[str], timeout: int = 5) -> Optional[str]:
    """Execute command safely and return first line of output or None."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = (res.stdout or res.stderr).splitlines()
        for line in out:
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("WARNING:"):
                return cleaned
        return None
    except Exception:
        return None

def check_tool(bin_name: str, version_args: List[str]) -> Dict[str, Any]:
    """Check if a tool exists on PATH and retrieve its version."""
    path = shutil.which(bin_name)
    if not path:
        return {
            "installed": False,
            "version": None,
            "path": None,
            "status": "MISSING"
        }
    version_str = run_cmd([path] + version_args)
    return {
        "installed": True,
        "version": version_str if version_str else "Detected (no version string)",
        "path": path,
        "status": "AVAILABLE"
    }

def get_system_audit() -> Dict[str, Any]:
    """Audit underlying OS, kernel, CPU, and memory."""
    os_desc = run_cmd(["lsb_release", "-d"]) or platform.platform()
    if os_desc.startswith("Description:"):
        os_desc = os_desc.replace("Description:", "").strip()
        
    cpu_model = "Unknown"
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    cpu_model = line.split(":", 1)[1].strip()
                    break
    except Exception:
        pass

    mem_total = "Unknown"
    mem_avail = "Unknown"
    try:
        res = subprocess.run(["free", "-h"], capture_output=True, text=True)
        for line in res.stdout.splitlines():
            if line.startswith("Mem:"):
                parts = line.split()
                mem_total = parts[1]
                mem_avail = parts[6] if len(parts) > 6 else parts[3]
    except Exception:
        pass

    disk_info = run_cmd(["df", "-h", "/"])

    return {
        "os": os_desc,
        "kernel": platform.release(),
        "arch": platform.machine(),
        "cpu_model": cpu_model,
        "cpu_threads": os.cpu_count(),
        "ram_total": mem_total,
        "ram_available": mem_avail,
        "disk_root": disk_info
    }

def audit_all() -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {}
    snapshot["system"] = get_system_audit()

    # Python
    venv_path = os.path.expanduser("~/LLMorch/.venv")
    snapshot["python"] = {
        "system_version": sys.version.split()[0],
        "system_executable": sys.executable,
        "venv_exists": os.path.exists(venv_path),
        "venv_path": venv_path,
        "venv_python": os.path.join(venv_path, "bin", "python") if os.path.exists(venv_path) else None,
        "sqlite3_module": True
    }
    try:
        import sqlite3
        snapshot["python"]["sqlite3_version"] = sqlite3.sqlite_version
    except ImportError:
        snapshot["python"]["sqlite3_module"] = False
        snapshot["python"]["sqlite3_version"] = None

    # Node
    snapshot["node"] = {
        "node": check_tool("node", ["--version"]),
        "npm": check_tool("npm", ["--version"]),
        "npx": check_tool("npx", ["--version"])
    }

    # Agents
    snapshot["agents"] = {
        "claude": check_tool("claude", ["--version"]),
        "agy": check_tool("agy", ["--version"]),
        "antigravity": check_tool("antigravity", ["--version"]),
        "gemini": check_tool("gemini", ["--version"]),
        "codex": check_tool("codex", ["--version"]),
        "opencode": check_tool("opencode", ["--version"])
    }

    # Compilers / Build
    snapshot["compilers"] = {
        "gcc": check_tool("gcc", ["--version"]),
        "g++": check_tool("g++", ["--version"]),
        "clang": check_tool("clang", ["--version"]),
        "clang++": check_tool("clang++", ["--version"]),
        "lld": check_tool("lld", ["--version"]),
        "make": check_tool("make", ["--version"]),
        "cmake": check_tool("cmake", ["--version"]),
        "ninja": check_tool("ninja", ["--version"]),
        "pkg-config": check_tool("pkg-config", ["--version"]),
        "git": check_tool("git", ["--version"]),
        "bazel": check_tool("bazel", ["--version"]),
        "bazelisk": check_tool("bazelisk", ["version"]),
        "rustc": check_tool("rustc", ["--version"]),
        "cargo": check_tool("cargo", ["--version"]),
        "go": check_tool("go", ["version"]),
        "javac": check_tool("javac", ["-version"])
    }

    # Hardware / EDA Tools
    snapshot["hardware-tools"] = {
        "verilator": check_tool("verilator", ["--version"]),
        "yosys": check_tool("yosys", ["-V"]),
        "sby": check_tool("sby", ["--help"]),
        "boolector": check_tool("boolector", ["--version"]),
        "z3": check_tool("z3", ["--version"]),
        "slang": check_tool("slang", ["--version"]),
        "iverilog": check_tool("iverilog", ["-V"]),
        "verible-lint": check_tool("verible-verilog-lint", ["--version"]),
        "cocotb": check_tool("cocotb-config", ["--version"]),
        "gtkwave": check_tool("gtkwave", ["--version"]),
        "fusesoc": check_tool("fusesoc", ["--version"])
    }

    # Security Tools
    snapshot["security-tools"] = {
        "semgrep": check_tool("semgrep", ["--version"]),
        "codeql": check_tool("codeql", ["version"]),
        "gdb": check_tool("gdb", ["--version"]),
        "strace": check_tool("strace", ["--version"]),
        "ltrace": check_tool("ltrace", ["--version"]),
        "valgrind": check_tool("valgrind", ["--version"]),
        "binutils_objdump": check_tool("objdump", ["--version"]),
        "binutils_readelf": check_tool("readelf", ["--version"]),
        "binutils_strings": check_tool("strings", ["--version"]),
        "joern": check_tool("joern", ["--version"]),
        "afl-fuzz": check_tool("afl-fuzz", ["--version"]),
        "ghidra": check_tool("ghidra", ["--version"]),
        "hexstrike": check_tool("hexstrike", ["--version"])
    }

    # Containers / Sandbox
    snapshot["containers"] = {
        "docker": check_tool("docker", ["--version"]),
        "docker-compose": check_tool("docker-compose", ["--version"]),
        "podman": check_tool("podman", ["--version"])
    }

    # Storage & Database
    snapshot["database"] = {
        "python_sqlite3": snapshot["python"]["sqlite3_version"],
        "sqlite3_cli": check_tool("sqlite3", ["--version"]),
        "psql": check_tool("psql", ["--version"]),
        "redis-cli": check_tool("redis-cli", ["--version"]),
        "qdrant": check_tool("qdrant", ["--version"]),
        "chroma": check_tool("chroma", ["--version"])
    }

    # Protocol & Host Utilities
    snapshot["protocol_dependencies"] = {
        "curl": check_tool("curl", ["--version"]),
        "wget": check_tool("wget", ["--version"]),
        "openssl": check_tool("openssl", ["version"]),
        "jq": check_tool("jq", ["--version"]),
        "ripgrep": check_tool("rg", ["--version"]),
        "fd": check_tool("fd", ["--version"]) if shutil.which("fd") else check_tool("fdfind", ["--version"])
    }

    # Evaluation of V0 and V1 readiness
    v0_critical = [
        ("Python venv", snapshot["python"]["venv_exists"]),
        ("Python sqlite3", snapshot["python"]["sqlite3_module"]),
        ("Git", snapshot["compilers"]["git"]["installed"]),
        ("Verilator", snapshot["hardware-tools"]["verilator"]["installed"]),
        ("Yosys", snapshot["hardware-tools"]["yosys"]["installed"]),
        ("Sby", snapshot["hardware-tools"]["sby"]["installed"]),
        ("Boolector SMT", snapshot["hardware-tools"]["boolector"]["installed"]),
        ("Slang", snapshot["hardware-tools"]["slang"]["installed"]),
        ("Verible Lint", snapshot["hardware-tools"]["verible-lint"]["installed"]),
        ("FuseSoC", snapshot["hardware-tools"]["fusesoc"]["installed"]),
        ("Claude Code or AGY", snapshot["agents"]["claude"]["installed"] or snapshot["agents"]["agy"]["installed"]),
        ("GCC/G++", snapshot["compilers"]["gcc"]["installed"] and snapshot["compilers"]["g++"]["installed"]),
        ("Make", snapshot["compilers"]["make"]["installed"]),
        ("CMake", snapshot["compilers"]["cmake"]["installed"]),
        ("Ninja", snapshot["compilers"]["ninja"]["installed"]),
        ("JQ", snapshot["protocol_dependencies"]["jq"]["installed"]),
    ]

    v1_critical = [
        ("ripgrep", snapshot["protocol_dependencies"]["ripgrep"]["installed"]),
        ("fd", snapshot["protocol_dependencies"]["fd"]["installed"]),
        ("Bazel", snapshot["compilers"]["bazel"]["installed"]),
        ("Semgrep", snapshot["security-tools"]["semgrep"]["installed"]),
        ("CodeQL", snapshot["security-tools"]["codeql"]["installed"]),
        ("Z3", snapshot["hardware-tools"]["z3"]["installed"]),
        ("Cocotb", snapshot["hardware-tools"]["cocotb"]["installed"]),
        ("Gemini CLI", snapshot["agents"]["gemini"]["installed"]),
        ("Codex CLI", snapshot["agents"]["codex"]["installed"]),
        ("OpenCode", snapshot["agents"]["opencode"]["installed"]),
        ("Podman Container Sandbox", snapshot["containers"]["podman"]["installed"] or snapshot["containers"]["docker"]["installed"]),
        ("Clang Toolchain & Sanitizers", snapshot["compilers"]["clang"]["installed"])
    ]

    v0_ready = all(status for _, status in v0_critical)
    v1_ready = all(status for _, status in v1_critical)
    
    snapshot["status"] = {
        "v0_ready": v0_ready,
        "v0_checks": {name: status for name, status in v0_critical},
        "v1_ready": v1_ready,
        "v1_checks": {name: status for name, status in v1_critical}
    }

    manual_actions: List[Dict[str, str]] = []

    if not snapshot["containers"]["podman"]["installed"] and not snapshot["containers"]["docker"]["installed"]:
        manual_actions.append({
            "tool": "podman",
            "tier": "V1",
            "action": "sudo apt install -y podman",
            "reason": "Rootless OCI container execution sandbox for untrusted simulation and validator runs"
        })

    if not snapshot["compilers"]["clang"]["installed"]:
        manual_actions.append({
            "tool": "clang / llvm / lld",
            "tier": "V1",
            "action": "sudo apt install -y clang llvm lld",
            "reason": "Compiler sanitizers (ASan/UBSan/TSan), libFuzzer, and firmware/DIF compilation"
        })

    if not snapshot["security-tools"]["valgrind"]["installed"]:
        manual_actions.append({
            "tool": "valgrind",
            "tier": "V1",
            "action": "sudo apt install -y valgrind ltrace",
            "reason": "Dynamic memory analysis and shared library call tracing"
        })

    if not snapshot["database"]["sqlite3_cli"]["installed"]:
        manual_actions.append({
            "tool": "sqlite3 (CLI)",
            "tier": "V1",
            "action": "sudo apt install -y sqlite3",
            "reason": "CLI inspection tool for SQLite database (Python runtime already has sqlite3 3.46.1)"
        })

    snapshot["manual_actions_required"] = manual_actions
    return snapshot

def main():
    snapshot = audit_all()
    if "--json" in sys.argv:
        print(json.dumps(snapshot, indent=2))
        return

    print("==================================================")
    print("LLMorch SYSTEM READINESS AUDIT")
    print("==================================================")
    print(f"OS:        {snapshot['system']['os']} ({snapshot['system']['arch']})")
    print(f"Kernel:    {snapshot['system']['kernel']}")
    print(f"CPU:       {snapshot['system']['cpu_model']} ({snapshot['system']['cpu_threads']} threads)")
    print(f"Memory:    {snapshot['system']['ram_available']} available / {snapshot['system']['ram_total']} total")
    print("--------------------------------------------------")
    print(f"Python:    {snapshot['python']['system_version']} (venv: {'OK' if snapshot['python']['venv_exists'] else 'MISSING'})")
    print(f"Database:  SQLite v{snapshot['python']['sqlite3_version']} (embedded runtime)")
    print(f"Agents:    Claude: {'OK' if snapshot['agents']['claude']['installed'] else 'MISSING'} | AGY: {'OK' if snapshot['agents']['agy']['installed'] else 'MISSING'}")
    print(f"           Gemini: {'OK' if snapshot['agents']['gemini']['installed'] else 'MISSING'} | Codex: {'OK' if snapshot['agents']['codex']['installed'] else 'MISSING'} | OpenCode: {'OK' if snapshot['agents']['opencode']['installed'] else 'MISSING'}")
    print(f"Search:    Ripgrep: {'OK' if snapshot['protocol_dependencies']['ripgrep']['installed'] else 'MISSING'} | FD: {'OK' if snapshot['protocol_dependencies']['fd']['installed'] else 'MISSING'}")
    print(f"Build:     Bazel: {'OK' if snapshot['compilers']['bazel']['installed'] else 'MISSING'} | GCC/G++: {'OK' if snapshot['compilers']['gcc']['installed'] else 'MISSING'}")
    print(f"Analysis:  Semgrep: {'OK' if snapshot['security-tools']['semgrep']['installed'] else 'MISSING'} | CodeQL: {'OK' if snapshot['security-tools']['codeql']['installed'] else 'MISSING'}")
    print(f"EDA/HW:    Verilator: {'OK' if snapshot['hardware-tools']['verilator']['installed'] else 'MISSING'} | Yosys: {'OK' if snapshot['hardware-tools']['yosys']['installed'] else 'MISSING'} | Sby: {'OK' if snapshot['hardware-tools']['sby']['installed'] else 'MISSING'}")
    print(f"           Z3: {'OK' if snapshot['hardware-tools']['z3']['installed'] else 'MISSING'} | Boolector: {'OK' if snapshot['hardware-tools']['boolector']['installed'] else 'MISSING'} | Slang: {'OK' if snapshot['hardware-tools']['slang']['installed'] else 'MISSING'}")
    print(f"           Verible: {'OK' if snapshot['hardware-tools']['verible-lint']['installed'] else 'MISSING'} | Cocotb: {'OK' if snapshot['hardware-tools']['cocotb']['installed'] else 'MISSING'} | FuseSoC: {'OK' if snapshot['hardware-tools']['fusesoc']['installed'] else 'MISSING'}")
    print(f"Sandbox:   Docker: {'OK' if snapshot['containers']['docker']['installed'] else 'MISSING'} | Podman: {'OK' if snapshot['containers']['podman']['installed'] else 'MISSING'}")
    print("--------------------------------------------------")
    print(f"V0 Slice Readiness: {'>>> READY <<<' if snapshot['status']['v0_ready'] else '>>> INCOMPLETE <<<'}")
    print(f"V1 Stack Readiness: {'>>> READY <<<' if snapshot['status']['v1_ready'] else '>>> PARTIAL (Container Sandbox pending) <<<'}")
    print("--------------------------------------------------")
    if snapshot["manual_actions_required"]:
        print(f"Recommended Actions for System Hardening ({len(snapshot['manual_actions_required'])} items):")
        for item in snapshot["manual_actions_required"]:
            print(f"  - [{item['tier']}] {item['tool']}: {item['action']}")
    print("==================================================")

if __name__ == "__main__":
    main()
