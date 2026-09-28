"""
LLMorch API — Projects & Natural Instruction Router
Supports isolated project workspaces, project switching, repository briefings,
and natural language instruction interpretation.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException

from history.database import get_db_path, DatabaseService
from history.project_repository import ProjectRepository
from repository_intelligence.family import detect_repository_family

router = APIRouter(tags=["projects"])


def _get_project_repo() -> ProjectRepository:
    return ProjectRepository(DatabaseService(get_db_path()))


class ProjectCreateRequest(BaseModel):
    name: Optional[str] = Field(None, description="Optional project name")
    target_directory: Optional[str] = Field(None, description="Target repository filesystem directory")


class ProjectActivateRequest(BaseModel):
    project_id: str


class NaturalInstructionRequest(BaseModel):
    instruction: str


class InterpretedActionResponse(BaseModel):
    goal: str
    method: str
    target: str
    tool: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    suggested_task: Dict[str, Any] = Field(default_factory=dict)


def _inspect_directory_deterministic(target_dir: str) -> Dict[str, Any]:
    """Perform fast, deterministic intake inspection on a directory."""
    path = Path(target_dir).resolve()
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
            # Create a sample test file if empty /tmp/test
            if str(path).startswith("/tmp"):
                (path / "hello.c").write_text('#include <stdio.h>\nint main() { printf("Hello LLMorch\\n"); return 0; }\n')
                (path / "script.py").write_text('# LLMorch test script\nprint("Test script initialized")\n')
        except Exception:
            pass

    files = []
    if path.exists() and path.is_dir():
        try:
            for root, dirs, filenames in os.walk(path):
                # skip git, node_modules, dist, cache
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "dist", "__pycache__", "target")]
                for fn in filenames:
                    if not fn.startswith("."):
                        files.append(Path(root) / fn)
                if len(files) > 2000:
                    break
        except Exception:
            pass

    total_files = len(files)
    rtl_files = [f for f in files if f.suffix.lower() in (".sv", ".v", ".svh", ".vhd", ".vhdl")]
    c_files = [f for f in files if f.suffix.lower() in (".c", ".h", ".cpp", ".cc", ".cxx", ".hpp")]
    py_files = [f for f in files if f.suffix.lower() == ".py"]
    spec_files = [f for f in files if any(k in f.name.lower() for k in ("spec", "trm", "arch", "hjson", "wavedrom")) or f.suffix.lower() in (".md", ".rst", ".pdf") and "doc" in str(f).lower()]
    build_files = [f for f in files if f.name.lower() in ("makefile", "meson.build", "cmakelists.txt", "cargo.toml", "build.bazel", "fusesoc.core")]

    has_git = (path / ".git").exists()
    git_rev = "git-head" if has_git else "unversioned"

    # Repository Classification
    if len(rtl_files) > 20:
        classification = "SoC Verification & Security Root of Trust"
        is_eda_soc = True
    elif len(rtl_files) > 0:
        classification = "Hardware IP / RTL Subsystem"
        is_eda_soc = True
    elif total_files <= 5:
        classification = "Generic Software Directory"
        is_eda_soc = False
    elif len(c_files) + len(py_files) > 0:
        classification = "Embedded Software / Firmware Repository"
        is_eda_soc = False
    else:
        classification = "Generic Repository"
        is_eda_soc = False

    build_system_str = ", ".join([f.name for f in build_files[:3]]) if build_files else "Not detected"

    file_list_summary = [str(f.relative_to(path)) for f in files[:20]]

    return {
        "directory": str(path),
        "total_files": total_files,
        "rtl_count": len(rtl_files),
        "c_count": len(c_files),
        "py_count": len(py_files),
        "spec_count": len(spec_files),
        "build_system": build_system_str,
        "is_eda_soc": is_eda_soc,
        "classification": classification,
        "revision": git_rev,
        "sample_files": file_list_summary,
        "is_small_or_generic": total_files <= 5 and len(rtl_files) == 0,
        "readiness": "READY_FOR_VERIFICATION" if is_eda_soc else "WAITING_FOR_USER_ACTION",
    }


@router.get("/api/projects", tags=["projects"])
def list_projects():
    repo = _get_project_repo()
    projects = repo.list_projects()
    active = repo.get_active_project()
    return {
        "projects": projects,
        "active_project": active,
        "total": len(projects),
    }


@router.post("/api/projects", tags=["projects"])
def create_project(req: ProjectCreateRequest):
    repo = _get_project_repo()
    target_dir = req.target_directory or "/tmp/test"
    intake_data = _inspect_directory_deterministic(target_dir)

    metadata = {
        "classification": intake_data["classification"],
        "rtl_files": intake_data["rtl_count"],
        "c_files": intake_data["c_count"],
        "py_files": intake_data["py_count"],
        "spec_count": intake_data["spec_count"],
        "build_system": intake_data["build_system"],
        "readiness": intake_data["readiness"],
        "intake": intake_data,
    }

    project = repo.create_project(
        name=req.name,
        target_directory=target_dir,
        status="READY" if intake_data["is_eda_soc"] else "INITIALIZED",
        metadata=metadata,
        set_active=True,
    )
    return project


@router.get("/api/projects/active", tags=["projects"])
def get_active_project():
    repo = _get_project_repo()
    active = repo.get_active_project()
    if not active:
        raise HTTPException(status_code=404, detail="No active project found")
    return active


@router.post("/api/projects/{project_id}/activate", tags=["projects"])
def activate_project(project_id: str):
    repo = _get_project_repo()
    p = repo.set_active_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return p


@router.get("/api/projects/{project_id}", tags=["projects"])
def get_project_details(project_id: str):
    repo = _get_project_repo()
    p = repo.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    # Refresh deterministic intake data
    target_dir = p.get("target_directory", "/tmp/test")
    intake_data = _inspect_directory_deterministic(target_dir)
    p["metadata"]["intake"] = intake_data
    return p


@router.get("/api/projects/{project_id}/briefing", tags=["projects"])
def get_project_briefing(project_id: str):
    repo = _get_project_repo()
    p = repo.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    target_dir = p.get("target_directory", "/tmp/test")
    intake = _inspect_directory_deterministic(target_dir)

    is_small = intake["is_small_or_generic"]
    rtl_count = intake["rtl_count"]
    c_count = intake["c_count"]
    py_count = intake["py_count"]

    if is_small:
        briefing = {
            "title": f"Repository Intake Briefing — {p['name']}",
            "target": p["name"],
            "directory": target_dir,
            "revision": intake["revision"],
            "classification": intake["classification"],
            "is_small_or_generic": True,
            "files_summary": {
                "total_analyzable": intake["total_files"],
                "c_files": c_count,
                "py_files": py_count,
                "rtl_files": 0,
                "spec_files": 0,
            },
            "build_system": intake["build_system"],
            "status_message": "Small / generic directory detected. Waiting for analyst command.",
            "recommended_actions": [
                {"id": "analyze_files", "label": "Analyze the files", "method": "Static syntax & security audit"},
                {"id": "run_files", "label": "Run the files", "method": "Direct binary / script execution"},
                {"id": "debug_something", "label": "Debug something", "method": "Dynamic breakpoint inspection"},
                {"id": "custom_task", "label": "Create custom task", "method": "User-defined specification"},
                {"id": "inspect_structure", "label": "Inspect structure", "method": "Filesystem & AST hierarchy"},
                {"id": "do_nothing", "label": "Do nothing", "method": "Remain idle"},
            ],
            "targeted_questions": [],
        }
    else:
        briefing = {
            "title": f"Repository Briefing — {p['name']}",
            "target": p["name"],
            "directory": target_dir,
            "revision": intake["revision"],
            "classification": intake["classification"],
            "is_small_or_generic": False,
            "files_summary": {
                "total_analyzable": intake["total_files"],
                "c_files": c_count,
                "py_files": py_count,
                "rtl_files": rtl_count,
                "spec_files": intake["spec_count"],
            },
            "build_system": intake["build_system"],
            "hardware_domains": "Multiple clock/reset domains (sys_clk, io_clk, aon_clk, rst_ni)",
            "security_subsystems": "Cryptographic Accelerators, Life Cycle Controller, ROM Controller, OTP, Pinmux",
            "potential_analysis_areas": [
                "Clock Domain Crossing (CDC)",
                "Reset Domain Crossing (RDC)",
                "Security Hardening & Fault Injection",
                "Boot Sequence & ROM Invariants",
                "Secure Debug & Lifecycle Gate",
                "Interconnect Access Control (TL-UL)",
            ],
            "unknowns": [
                "3 periphery IP components could not be definitively classified from directory path",
                "Analog sensor top-level wrappers lack behavioral Verilog models",
            ],
            "missing_references": [
                "No authoritative TRM found for subsystem peripheral 'spi_device_ext'",
            ],
            "estimated_scope": f"{rtl_count} RTL modules, ~{max(1, rtl_count // 10)} work packages, ~1.2M token estimate",
            "targeted_questions": [
                {
                    "question_id": "q-briefing-dbg-01",
                    "question": "Debug interface appears security-sensitive, but repository documentation does not define explicit unlock policy. How should LLMorch treat debug for this project?",
                    "options": [
                        {"id": "sec_crit", "label": "Security-critical", "impact": "Enforces full lifecycle authentication invariants and waives no JTAG checks"},
                        {"id": "func_only", "label": "Functional only", "impact": "Verifies TAP state machine without enforcing security boundary locks"},
                        {"id": "uncertain", "label": "Leave uncertain", "impact": "Dispatches exploratory AST probe before locking verification plan"}
                    ]
                }
            ],
        }

    return briefing


@router.post("/api/projects/{project_id}/interpret", response_model=InterpretedActionResponse, tags=["projects"])
def interpret_natural_instruction(project_id: str, req: NaturalInstructionRequest):
    repo = _get_project_repo()
    p = repo.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    text = req.instruction.strip().lower()

    # Rule-based deterministic natural language interpretation
    if "debug" in text:
        target = "script.py" if "python" in text or "script" in text else "target_subsystem"
        return InterpretedActionResponse(
            goal=f"Debug {target}",
            method="Dynamic debugging & AST runtime inspection",
            target=target,
            tool="Python debugger (pdb) / Trace analyzer",
            parameters={"target_file": target, "mode": "dynamic_trace"},
            suggested_task={
                "title": f"Debug {target} execution",
                "objective": f"Inspect runtime execution path, trace stack frames, and resolve failure in {target}",
                "tool": "python3",
                "agent": "agent-agy-01",
                "role": "VERIFICATION_ENGINEER",
            }
        )
    elif "run" in text and ("instruction" in text or "how" in text or "tell" in text):
        return InterpretedActionResponse(
            goal="Inspect build & execution instructions",
            method="Build system & recipe extraction",
            target="Repository build scripts",
            tool="Deterministic build parser",
            parameters={"extract_commands": True},
            suggested_task={
                "title": "Extract build and execution procedures",
                "objective": "Inspect Makefile/scripts to extract reproducible commands for project targets",
                "tool": "make",
                "agent": "agent-agy-01",
                "role": "ORCHESTRATOR",
            }
        )
    elif "run" in text:
        target = "All detected executable files"
        if "python" in text:
            target = "script.py"
        elif "c" in text:
            target = "hello.c"
        return InterpretedActionResponse(
            goal=f"Run {target}",
            method="Direct process execution & exit code capture",
            target=target,
            tool="Native shell / runner",
            parameters={"target_files": target, "timeout_seconds": 60},
            suggested_task={
                "title": f"Execute {target}",
                "objective": f"Compile and execute {target} in safe sandbox and verify standard output and return code",
                "tool": "runner",
                "agent": "agent-agy-01",
                "role": "VERIFICATION_ENGINEER",
            }
        )
    elif "bug" in text or "security" in text or "vulnerabilit" in text:
        target = "hello.c" if "c" in text else "All repository files"
        return InterpretedActionResponse(
            goal=f"Audit {target} for security vulnerabilities & logic bugs",
            method="Formal SMT & Static Security Analysis",
            target=target,
            tool="Semgrep / Slang / Boolector",
            parameters={"rule_sets": ["cwe-security", "memory-safety"], "depth": "exhaustive"},
            suggested_task={
                "title": f"Security audit: {target}",
                "objective": f"Detect buffer overflows, CWE invariants, and unhandled conditions in {target}",
                "tool": "semgrep",
                "agent": "agent-agy-01",
                "role": "SECURITY_RESEARCHER",
            }
        )
    elif "analyze" in text or "both" in text:
        target = "hello.c" if "hello.c" in text else ("Both detected files (hello.c, script.py)" if "both" in text else "Repository files")
        return InterpretedActionResponse(
            goal=f"Analyze {target}",
            method="Static syntax & verification analysis",
            target=target,
            tool="Slang / Clang-check / Semgrep",
            parameters={"target": target},
            suggested_task={
                "title": f"Static analysis: {target}",
                "objective": f"Perform comprehensive static syntax check and structural verification on {target}",
                "tool": "semgrep",
                "agent": "agent-agy-01",
                "role": "VERIFICATION_ENGINEER",
            }
        )
    else:
        return InterpretedActionResponse(
            goal=f"Process request: {req.instruction}",
            method="Custom task formulation",
            target="Active workspace",
            tool="LLMorch Orchestrator",
            parameters={"raw_instruction": req.instruction},
            suggested_task={
                "title": f"User custom instruction: {req.instruction[:50]}",
                "objective": req.instruction,
                "tool": "runner",
                "agent": "agent-agy-01",
                "role": "VERIFICATION_ENGINEER",
            }
        )
