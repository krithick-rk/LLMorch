"""
LLMorch — Language-Aware Tool Routing & Explainability Engine
Selects candidate tools based on language, component family, and analysis method.
Explains selections and explicit tool rejections (Section 4, 5).
"""

from __future__ import annotations

import shutil
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolDecision(BaseModel):
    tool_name: str
    selected: bool
    command_template: List[str]
    rationale: str


class AnalysisMethodExplanation(BaseModel):
    target: str
    detected_language: str
    component_type: str
    recommended_tools: List[str]
    selection_rationale: str
    rejected_tools: List[Dict[str, str]]
    analysis_method: str
    primary_tool: str
    primary_command: List[str]


def route_tools_for_scope(
    target_path: str,
    intake_metadata: Dict[str, Any],
    task_intent: Optional[str] = None
) -> AnalysisMethodExplanation:
    """
    Deterministically computes language-aware tool routing and generates an explainable rationale.
    """
    lang = intake_metadata.get("primary_language", "Unknown")
    comp_type = intake_metadata.get("classification", "Generic Repository")
    rtl_count = intake_metadata.get("rtl_count", 0)
    rust_count = intake_metadata.get("rust_count", 0)
    c_count = intake_metadata.get("c_count", 0)
    has_cargo = "cargo" in intake_metadata.get("build_system", "").lower()

    recommended_tools: List[str] = []
    rejected_tools: List[Dict[str, str]] = []
    primary_tool = "rust_source_inspector"
    primary_cmd = ["python3", "-m", "repository_intelligence.rust_security_scanner", target_path]
    analysis_method = "Source & Semantic Invariant Inspection"

    if rust_count > 0 and rtl_count == 0:
        # Pure Rust component / firmware (Section 4)
        recommended_tools = [
            "rust_source_inspector",
            "ripgrep (rg)",
            "deterministic_reproducer",
        ]
        if shutil.which("cargo"):
            recommended_tools.extend(["cargo metadata", "cargo check", "cargo test"])

        rejected_tools.append({
            "tool": "yosys",
            "reason": "No RTL detected in selected scope (pure Rust firmware component)"
        })
        rejected_tools.append({
            "tool": "verilator",
            "reason": "No RTL / SystemVerilog inputs detected in selected scope"
        })
        rejected_tools.append({
            "tool": "boolector",
            "reason": "Hardware SMT formal solver not applicable to pure firmware crate without formal RTL contract"
        })

        selection_rationale = f"Rust firmware component with {intake_metadata.get('build_system', 'Cargo')}. Analysis routed to semantic AST/pattern inspection and deterministic reproducer harnesses."
        primary_tool = "rust_source_inspector"
        analysis_method = "Firmware Security & Semantic Invariant Analysis"

    elif rtl_count > 0 and rust_count == 0 and c_count == 0:
        # Pure RTL
        recommended_tools = ["verilator", "yosys"]
        if shutil.which("boolector"):
            recommended_tools.append("boolector")

        rejected_tools.append({
            "tool": "cargo",
            "reason": "No Rust source files detected in selected scope"
        })
        rejected_tools.append({
            "tool": "clang",
            "reason": "No C/C++ source files detected in selected scope"
        })

        selection_rationale = "RTL hardware design. Analysis routed to Verilator lint and Yosys synthesis/formal checks."
        primary_tool = "verilator" if shutil.which("verilator") else "yosys"
        primary_cmd = [primary_tool, "--version"]
        analysis_method = "Hardware IP / RTL Synthesis & Formal Verification"

    elif rtl_count > 0 and (rust_count > 0 or c_count > 0):
        # Mixed Hardware & Software (Section 28)
        recommended_tools = ["verilator", "yosys", "rust_source_inspector", "ripgrep (rg)"]
        selection_rationale = "Mixed Hardware / Firmware repository. Routed to concurrent RTL verification and firmware security inspection."
        primary_tool = "rust_source_inspector" if rust_count > rtl_count else ("verilator" if shutil.which("verilator") else "yosys")
        primary_cmd = [primary_tool, "--version"] if primary_tool in ("verilator", "yosys") else ["python3", "-m", "repository_intelligence.rust_security_scanner", target_path]
        analysis_method = "Cross-Component HW/SW Interface & Security Analysis"

    elif c_count > 0:
        # C / C++ firmware
        recommended_tools = ["clang-check", "ripgrep (rg)", "deterministic_reproducer"]
        rejected_tools.append({
            "tool": "yosys",
            "reason": "No RTL detected in selected scope"
        })
        selection_rationale = "C/C++ firmware repository. Routed to semantic source analysis and static verification."
        primary_tool = "ripgrep (rg)"
        primary_cmd = ["rg", "--version"]
        analysis_method = "C/C++ Static Firmware Security Audit"

    else:
        # Generic
        recommended_tools = ["ripgrep (rg)", "python3"]
        rejected_tools.append({
            "tool": "yosys",
            "reason": "No RTL detected in selected scope"
        })
        selection_rationale = "Generic repository. Routed to multi-pattern text analysis."
        primary_tool = "ripgrep (rg)"
        primary_cmd = ["rg", "--version"]
        analysis_method = "Generic Structural Source Analysis"

    return AnalysisMethodExplanation(
        target=target_path,
        detected_language=lang,
        component_type=comp_type,
        recommended_tools=recommended_tools,
        selection_rationale=selection_rationale,
        rejected_tools=rejected_tools,
        analysis_method=analysis_method,
        primary_tool=primary_tool,
        primary_command=primary_cmd
    )
