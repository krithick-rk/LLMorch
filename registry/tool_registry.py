"""
LLMorch Tool Registry (Phase 9.3)
Authoritative registry of security, analysis, synthesis, simulation, and verification tools.
Supports categorization, capability tracking, status resolution, and execution lineage.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid


class ToolDefinition(BaseModel):
    tool_name: str
    display_name: str
    category: str  # RTL, Static Analysis, Dynamic Analysis, Binary Analysis, Formal, Simulation, Fuzzing, Repository Intelligence, Security Scanning, General
    version: str
    description: str
    capabilities: List[str] = Field(default_factory=list)
    command_template: str
    enabled: bool = True
    health: str = "HEALTHY"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolRegistry:
    """
    Authoritative Tool Registry.
    Provides registry metadata for all available analysis tools.
    """

    def __init__(self, populate_defaults: bool = True):
        self._tools: Dict[str, ToolDefinition] = {}
        if populate_defaults:
            self._register_default_tools()

    def register_tool(self, tool: ToolDefinition) -> None:
        self._tools[tool.tool_name] = tool

    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        return self._tools.get(tool_name)

    def list_tools(self, category: Optional[str] = None) -> List[ToolDefinition]:
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category.lower() == category.lower()]
        return sorted(tools, key=lambda t: (t.category, t.display_name))

    def list_categories(self) -> List[str]:
        cats = sorted(list(set(t.category for t in self._tools.values())))
        return cats

    def _register_default_tools(self) -> None:
        defaults = [
            # 1. RTL
            ToolDefinition(
                tool_name="verilator",
                display_name="Verilator",
                category="RTL",
                version="5.020",
                description="Fast open-source Verilog/SystemVerilog simulator and C++ model generator.",
                capabilities=["rtl_simulation", "linting", "c_model_generation", "coverage_analysis"],
                command_template="verilator --cc --exe {source_files} --top-module {top}",
            ),
            ToolDefinition(
                tool_name="yosys",
                display_name="Yosys Open SYnthesis Suite",
                category="RTL",
                version="0.38",
                description="Framework for RTL synthesis and formal verification front-end.",
                capabilities=["rtl_synthesis", "netlist_generation", "formal_equivalence", "fsm_extraction"],
                command_template="yosys -p 'read_verilog {source_files}; synth -top {top}'",
            ),
            ToolDefinition(
                tool_name="verible",
                display_name="Verible",
                category="RTL",
                version="0.0-3622",
                description="Suite of SystemVerilog development tools: parser, style linter, indexer.",
                capabilities=["systemverilog_lint", "formatting", "syntax_tree", "indexer"],
                command_template="verible-verilog-lint {source_files}",
            ),
            ToolDefinition(
                tool_name="slang",
                display_name="Slang",
                category="RTL",
                version="3.0",
                description="Modern SystemVerilog compiler, elaborator, and AST extractor.",
                capabilities=["ast_extraction", "strict_elaboration", "preprocessor", "syntax_validation"],
                command_template="slang --lint-only {source_files}",
            ),

            # 2. Static Analysis
            ToolDefinition(
                tool_name="semgrep",
                display_name="Semgrep",
                category="Static Analysis",
                version="1.65.0",
                description="Fast, lightweight static analysis engine for code patterns and security taint.",
                capabilities=["c_security_rules", "python_taint", "custom_yaml_rules", "secret_patterns"],
                command_template="semgrep --config {ruleset} {target_dir}",
            ),
            ToolDefinition(
                tool_name="codeql",
                display_name="CodeQL",
                category="Static Analysis",
                version="2.16.2",
                description="Semantic code analysis engine queryable via QL for deep inter-procedural bugs.",
                capabilities=["cross_function_taint", "dataflow_analysis", "path_queries", "memory_safety"],
                command_template="codeql database analyze {db_path} {query_suite}",
            ),
            ToolDefinition(
                tool_name="clang-tidy",
                display_name="Clang-Tidy",
                category="Static Analysis",
                version="18.1.0",
                description="Clang-based C++ linter and static analyzer.",
                capabilities=["cert_c_rules", "bugprone_checks", "memory_safety", "undefined_behavior"],
                command_template="clang-tidy -p {compile_commands} {source_files}",
            ),

            # 3. Dynamic Analysis
            ToolDefinition(
                tool_name="valgrind",
                display_name="Valgrind Memcheck",
                category="Dynamic Analysis",
                version="3.22.0",
                description="Dynamic memory debugging and leak detection suite.",
                capabilities=["memcheck", "leak_detection", "use_after_free", "uninitialized_reads"],
                command_template="valgrind --tool=memcheck --leak-check=full {executable}",
            ),
            ToolDefinition(
                tool_name="asan",
                display_name="AddressSanitizer (ASan)",
                category="Dynamic Analysis",
                version="18.1.0",
                description="Fast compiler instrumentation for memory error detection.",
                capabilities=["buffer_overflow", "stack_out_of_bounds", "heap_uaf", "double_free"],
                command_template="gcc -fsanitize=address -g {source_files} -o {output}",
            ),
            ToolDefinition(
                tool_name="gdb",
                display_name="GNU Debugger (GDB)",
                category="Dynamic Analysis",
                version="14.2",
                description="Interactive and scriptable machine-level debugger.",
                capabilities=["core_dump_inspection", "breakpoint_analysis", "register_state", "backtrace"],
                command_template="gdb -batch -ex 'run' -ex 'bt' {executable}",
            ),

            # 4. Binary Analysis
            ToolDefinition(
                tool_name="ghidra",
                display_name="Ghidra Headless Analyzer",
                category="Binary Analysis",
                version="11.0",
                description="NSA-developed software reverse engineering framework.",
                capabilities=["decompilation", "control_flow_graph", "symbol_recovery", "xref_analysis"],
                command_template="ghidra-headless {project_dir} {project_name} -import {binary_path}",
            ),
            ToolDefinition(
                tool_name="objdump",
                display_name="GNU objdump",
                category="Binary Analysis",
                version="2.42",
                description="Inspects executable headers, symbols, and disassembles machine code.",
                capabilities=["elf_parsing", "section_analysis", "rodata_dump", "symbol_table"],
                command_template="objdump -d -s {binary_path}",
            ),

            # 5. Formal
            ToolDefinition(
                tool_name="z3",
                display_name="Z3 Theorem Prover",
                category="Formal",
                version="4.13.0",
                description="High-performance SMT solver for satisfiability and formal proofs.",
                capabilities=["sat_checking", "bitvector_arithmetic", "counterexample_generation", "smt2_solver"],
                command_template="z3 -smt2 {smt_formula}",
            ),
            ToolDefinition(
                tool_name="symbi-yosys",
                display_name="SymbiYosys (sby)",
                category="Formal",
                version="0.38",
                description="Formal hardware verification front-end for bounded model checking and k-induction.",
                capabilities=["bmc_bounded_model_checking", "induction", "cover_traces", "assert_checker"],
                command_template="sby -f {sby_file}",
            ),

            # 6. Simulation
            ToolDefinition(
                tool_name="cocotb",
                display_name="Cocotb",
                category="Simulation",
                version="1.8.1",
                description="Coroutine-based Python testbench environment for hardware simulation.",
                capabilities=["stimulus_generation", "regression_harness", "waveform_analysis", "co_simulation"],
                command_template="pytest -v test_runner.py",
            ),

            # 7. Fuzzing
            ToolDefinition(
                tool_name="aflplusplus",
                display_name="AFL++",
                category="Fuzzing",
                version="4.20c",
                description="State-of-the-art coverage-guided feedback-driven fuzzer.",
                capabilities=["mutation_fuzzing", "crash_triage", "corpus_minimization", "dictionary_expansion"],
                command_template="afl-fuzz -i {input_corpus} -o {output_dir} -- {target_bin}",
            ),
            ToolDefinition(
                tool_name="libfuzzer",
                display_name="LLVM libFuzzer",
                category="Fuzzing",
                version="18.1.0",
                description="In-process, coverage-guided evolutionary fuzzing engine.",
                capabilities=["api_fuzzing", "memory_instrumentation", "dictionary_generation", "crash_reproducers"],
                command_template="{target_fuzzer} -max_total_time=60 -artifact_prefix={out}/",
            ),

            # 8. Repository Intelligence
            ToolDefinition(
                tool_name="repository_intelligence",
                display_name="LLMorch Repository Intelligence",
                category="Repository Intelligence",
                version="2.0",
                description="Deep hardware/software repository scanner, language classifier, and surface mapper.",
                capabilities=["family_detection", "language_breakdown", "security_surface_mapping", "analysis_units"],
                command_template="python3 -m repository_intelligence.scanner --path {repo_path}",
            ),

            # 9. Security Scanning
            ToolDefinition(
                tool_name="trivy",
                display_name="Trivy Vulnerability Scanner",
                category="Security Scanning",
                version="0.49.0",
                description="Comprehensive vulnerability, misconfiguration, and dependency scanner.",
                capabilities=["secret_quarantine", "cve_lookup", "license_audit", "dependency_check"],
                command_template="trivy fs --scanners vuln,secret,config {target_dir}",
            ),
            ToolDefinition(
                tool_name="gitleaks",
                display_name="Gitleaks",
                category="Security Scanning",
                version="8.18.2",
                description="Fast static analyzer for detecting and redacting secrets and private keys.",
                capabilities=["api_key_detection", "private_key_redaction", "commit_history_scan"],
                command_template="gitleaks detect --source {target_dir} --no-git",
            ),

            # 10. General
            ToolDefinition(
                tool_name="sandbox_engine",
                display_name="LLMorch Sandbox Engine",
                category="General",
                version="1.0.0",
                description="Rootless container isolation sandbox for deterministic PoC and test execution.",
                capabilities=["ephemeral_isolation", "stdout_stderr_capture", "resource_capping", "timeout_enforcement"],
                command_template="llmorch-sandbox run --timeout 30 -- {command}",
            ),
        ]

        for t in defaults:
            self.register_tool(t)


# Singleton
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry(populate_defaults=True)
    return _tool_registry
