"""
LLMorch Deterministic Repository Preflight & Inventory Analyzer
Performs zero-cost deterministic analysis of target repositories before launching expensive agent workflows.
Prevents infinite loops and runaway token estimates on empty repositories, 0-byte files, and unanalyzable trees.
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class RepositoryClassification(str):
    EMPTY_REPOSITORY = "EMPTY_REPOSITORY"
    INSUFFICIENT_ANALYZABLE_CONTENT = "INSUFFICIENT_ANALYZABLE_CONTENT"
    UNSUPPORTED_ONLY = "UNSUPPORTED_ONLY"
    DOCUMENTATION_ONLY = "DOCUMENTATION_ONLY"
    BINARY_ONLY = "BINARY_ONLY"
    SOFTWARE_ONLY = "SOFTWARE_ONLY"
    SOURCE_WITHOUT_BUILD_SYSTEM = "SOURCE_WITHOUT_BUILD_SYSTEM"
    RTL_ONLY = "RTL_ONLY"
    MIXED_SOC = "MIXED_SOC"
    MIXED_RTL_SOFTWARE = "MIXED_SOC"
    GENERIC_REPOSITORY = "GENERIC_REPOSITORY"


class TerminalIntakeStatus(str):
    COMPLETED_NO_ANALYZABLE_CONTENT = "COMPLETED_NO_ANALYZABLE_CONTENT"
    COMPLETED_UNSUPPORTED_CONTENT = "COMPLETED_UNSUPPORTED_CONTENT"
    COMPLETED_SPECIFICATION_ONLY = "COMPLETED_SPECIFICATION_ONLY"
    COMPLETED_BINARY_ONLY = "COMPLETED_BINARY_ONLY"
    READY_FOR_ANALYSIS = "READY_FOR_ANALYSIS"


class PreflightReport(BaseModel):
    repository_path: str
    files_discovered: int = 0
    directories_discovered: int = 0
    total_bytes: int = 0
    zero_byte_files_count: int = 0
    analyzable_files_count: int = 0
    unsupported_files_count: int = 0
    recognized_languages: List[str] = Field(default_factory=list)
    rtl_detected: bool = False
    software_detected: bool = False
    build_system_detected: bool = False
    build_systems: List[str] = Field(default_factory=list)
    specifications_detected: bool = False
    specifications_count: int = 0
    test_infra_detected: bool = False
    classification: str = RepositoryClassification.INSUFFICIENT_ANALYZABLE_CONTENT
    terminal_status: str = TerminalIntakeStatus.COMPLETED_NO_ANALYZABLE_CONTENT
    analysis_feasibility: str = "INSUFFICIENT_DATA"
    is_terminal: bool = True  # If true, analysis stops immediately without spawning LLM tasks
    estimated_tokens: int = 0
    suggested_actions: List[str] = Field(default_factory=list)
    summary_text: str = ""
    file_inventory: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def total_files(self) -> int:
        return self.files_discovered

    @property
    def zero_byte_file_count(self) -> int:
        return self.zero_byte_files_count

    @property
    def analyzable_file_count(self) -> int:
        return self.analyzable_files_count

    @property
    def has_rtl(self) -> bool:
        return self.rtl_detected

    @property
    def has_software(self) -> bool:
        return self.software_detected

    @property
    def has_build_system(self) -> bool:
        return self.build_system_detected

    @property
    def has_specifications(self) -> bool:
        return self.specifications_detected


SUPPORTED_CODE_EXTENSIONS = {
    ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++", ".cc": "C++",
    ".rs": "Rust", ".go": "Go", ".py": "Python",
}

SUPPORTED_RTL_EXTENSIONS = {
    ".sv": "SystemVerilog", ".v": "Verilog", ".vhd": "VHDL", ".vhdl": "VHDL", ".svh": "SystemVerilog"
}

SPECIFICATION_EXTENSIONS = {
    ".pdf": "PDF", ".md": "Markdown", ".txt": "Text", ".svd": "SVD", ".hjson": "Hjson", ".yaml": "YAML", ".json": "JSON"
}

BUILD_FILENAMES = {
    "BUILD", "BUILD.bazel", "WORKSPACE", "MODULE.bazel",
    "CMakeLists.txt", "Makefile", "makefile", "Cargo.toml",
    "Fusesoc.core", "meson.build"
}

BINARY_EXTENSIONS = {
    ".exe", ".so", ".dll", ".dylib", ".bin", ".elf", ".o", ".a", ".tar", ".gz", ".zip", ".png", ".jpg", ".jpeg"
}

IGNORED_DIRS = {".git", ".venv", "node_modules", "vendor", "third_party", "build", "dist", "target", ".cache", "__pycache__"}


def analyze_repository_preflight(repo_path: str) -> PreflightReport:
    """
    Deterministically audits the filesystem of target repo_path.
    Calculates inventory, byte counts, languages, and establishes explicit terminal state.
    """
    path = Path(repo_path).resolve()
    if not path.exists() or not path.is_dir():
        return PreflightReport(
            repository_path=repo_path,
            classification=RepositoryClassification.INSUFFICIENT_ANALYZABLE_CONTENT,
            terminal_status=TerminalIntakeStatus.COMPLETED_NO_ANALYZABLE_CONTENT,
            is_terminal=True,
            summary_text="Target repository path does not exist or is not a directory.",
            suggested_actions=["Check repository path and ensure directory exists."]
        )

    files_discovered = 0
    directories_discovered = 0
    total_bytes = 0
    zero_byte_count = 0
    analyzable_count = 0
    unsupported_count = 0
    languages_seen = set()
    build_systems_found = set()
    specs_count = 0
    has_rtl = False
    has_sw = False
    has_test_infra = False
    file_inventory = []

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        directories_discovered += len(dirs)

        for f in files:
            files_discovered += 1
            f_path = Path(root) / f
            rel_path = str(f_path.relative_to(path))
            
            try:
                st = f_path.stat()
                sz = st.st_size
            except Exception:
                sz = 0

            total_bytes += sz
            is_zero = (sz == 0)
            if is_zero:
                zero_byte_count += 1

            ext = f_path.suffix.lower()
            lang = None
            is_analyzable = False

            if f in BUILD_FILENAMES or f.endswith(".core"):
                build_systems_found.add(f)
                lang = "Build Metadata"
                if not is_zero:
                    is_analyzable = True

            elif ext in SUPPORTED_RTL_EXTENSIONS:
                has_rtl = True
                lang = SUPPORTED_RTL_EXTENSIONS[ext]
                languages_seen.add(lang)
                if not is_zero:
                    is_analyzable = True

            elif ext in SUPPORTED_CODE_EXTENSIONS:
                has_sw = True
                lang = SUPPORTED_CODE_EXTENSIONS[ext]
                languages_seen.add(lang)
                if not is_zero:
                    is_analyzable = True

            elif ext in SPECIFICATION_EXTENSIONS:
                specs_count += 1
                lang = SPECIFICATION_EXTENSIONS[ext]
                languages_seen.add(lang)
                if not is_zero:
                    is_analyzable = True

            elif ext in BINARY_EXTENSIONS:
                lang = "Binary"
                unsupported_count += 1

            else:
                lang = "Unknown"
                unsupported_count += 1

            if is_analyzable:
                analyzable_count += 1

            if any(term in rel_path.lower() for term in ("test", "tb", "sim", "cocotb", "verilator", "harness")):
                has_test_infra = True

            file_inventory.append({
                "path": rel_path,
                "size_bytes": sz,
                "language": lang,
                "is_zero_byte": is_zero,
                "is_analyzable": is_analyzable
            })

    # Determine classification and terminal state
    build_detected = len(build_systems_found) > 0
    specs_detected = specs_count > 0

    if files_discovered == 0:
        classification = RepositoryClassification.EMPTY_REPOSITORY
        terminal_status = TerminalIntakeStatus.COMPLETED_NO_ANALYZABLE_CONTENT
        is_terminal = True
        feasibility = "EMPTY_REPOSITORY"
        suggested_actions = [
            "Add source code (C/C++, Rust, Go, Python)",
            "Add RTL modules (SystemVerilog, Verilog, VHDL)",
        ]
        summary_text = "Repository is completely empty (0 files discovered)."

    elif analyzable_count == 0 and unsupported_count > 0:
        classification = RepositoryClassification.UNSUPPORTED_ONLY
        terminal_status = TerminalIntakeStatus.COMPLETED_UNSUPPORTED_CONTENT
        is_terminal = True
        feasibility = "UNSUPPORTED_FILE_FORMATS"
        suggested_actions = [
            "Convert files to supported formats (C/C++, SystemVerilog, Markdown, SVD)",
            "Specify custom analysis tool or wrapper",
            "Upload decompiled or parsed representations"
        ]
        summary_text = f"Repository contains {files_discovered} files of unsupported formats. Analysis terminated."

    elif total_bytes == 0 or analyzable_count == 0:
        classification = RepositoryClassification.INSUFFICIENT_ANALYZABLE_CONTENT
        terminal_status = TerminalIntakeStatus.COMPLETED_NO_ANALYZABLE_CONTENT
        is_terminal = True
        feasibility = "INSUFFICIENT_ANALYZABLE_CONTENT"
        suggested_actions = [
            "Add source code (C/C++, Rust, Go, Python)",
            "Add RTL modules (SystemVerilog, Verilog, VHDL)",
            "Provide build instructions or Makefile/BUILD files",
            "Add RM/TRM specification documents",
            "Specify a custom verification task",
            "Perform lightweight structural inspection"
        ]
        summary_text = (
            f"Repository contains {files_discovered} files ({total_bytes} bytes). "
            f"Analyzable content: 0 files. Run completed with no analyzable content."
        )

    elif analyzable_count > 0 and not has_rtl and not has_sw and specs_detected:
        classification = RepositoryClassification.DOCUMENTATION_ONLY
        terminal_status = TerminalIntakeStatus.COMPLETED_SPECIFICATION_ONLY
        is_terminal = True
        feasibility = "SPECIFICATION_INTAKE_ONLY"
        suggested_actions = [
            "Ingest RM/TRM specifications and extract requirements",
            "Generate draft verification plan from specifications",
            "Provide design implementation (RTL/Software) to link with specifications"
        ]
        summary_text = f"Repository contains {specs_count} specification document(s) with no RTL/Software implementation."

    elif has_rtl and has_sw:
        classification = RepositoryClassification.MIXED_SOC
        terminal_status = TerminalIntakeStatus.READY_FOR_ANALYSIS
        is_terminal = False
        feasibility = "HIGH_FEASIBILITY_SOC"
        suggested_actions = ["Run 23-Bucket SoC Verification Plan"]
        summary_text = f"Mixed SoC repository detected: RTL ({analyzable_count} files) and Software source."

    elif has_rtl and not has_sw:
        classification = RepositoryClassification.RTL_ONLY
        terminal_status = TerminalIntakeStatus.READY_FOR_ANALYSIS
        is_terminal = False
        feasibility = "HIGH_FEASIBILITY_RTL"
        suggested_actions = ["Run RTL Hardware Verification and Linting"]
        summary_text = f"RTL repository detected with {analyzable_count} hardware source files."

    elif has_sw and not has_rtl and not build_detected:
        classification = RepositoryClassification.SOURCE_WITHOUT_BUILD_SYSTEM
        terminal_status = TerminalIntakeStatus.READY_FOR_ANALYSIS
        is_terminal = False
        feasibility = "MODERATE_FEASIBILITY_NO_BUILD"
        suggested_actions = ["Provide Makefile or build configuration for complete analysis"]
        summary_text = f"Source code detected ({analyzable_count} files) without explicit build system."

    elif has_sw and not has_rtl:
        classification = RepositoryClassification.SOFTWARE_ONLY
        terminal_status = TerminalIntakeStatus.READY_FOR_ANALYSIS
        is_terminal = False
        feasibility = "HIGH_FEASIBILITY_SW"
        suggested_actions = ["Run Static Security Analysis and SAST"]
        summary_text = f"Software repository detected with {analyzable_count} source files."

    else:
        classification = RepositoryClassification.GENERIC_REPOSITORY
        terminal_status = TerminalIntakeStatus.READY_FOR_ANALYSIS
        is_terminal = False
        feasibility = "GENERIC_ANALYSIS"
        suggested_actions = ["Run General Security Surface Analysis"]
        summary_text = f"Generic repository with {analyzable_count} analyzable files."

    # Deterministic token estimation based on actual analyzable content
    # Empty files or repositories contribute 0 tokens.
    analyzable_bytes = sum(f["size_bytes"] for f in file_inventory if f["is_analyzable"])
    estimated_tokens = max(0, int(analyzable_bytes / 4)) if analyzable_count > 0 else 0

    return PreflightReport(
        repository_path=str(path),
        files_discovered=files_discovered,
        directories_discovered=directories_discovered,
        total_bytes=total_bytes,
        zero_byte_files_count=zero_byte_count,
        analyzable_files_count=analyzable_count,
        unsupported_files_count=unsupported_count,
        recognized_languages=sorted(list(languages_seen)),
        rtl_detected=has_rtl,
        software_detected=has_sw,
        build_system_detected=build_detected,
        build_systems=sorted(list(build_systems_found)),
        specifications_detected=specs_detected,
        specifications_count=specs_count,
        test_infra_detected=has_test_infra,
        classification=classification,
        terminal_status=terminal_status,
        analysis_feasibility=feasibility,
        is_terminal=is_terminal,
        estimated_tokens=estimated_tokens,
        suggested_actions=suggested_actions,
        summary_text=summary_text,
        file_inventory=file_inventory[:100]  # Store preview
    )


# Module-level aliases
inspect_repository_preflight = analyze_repository_preflight
PreflightClassification = RepositoryClassification
RepositoryClassification.MIXED_RTL_SOFTWARE = RepositoryClassification.MIXED_SOC
RepositoryClassification.SOURCE_WITHOUT_BUILD_SYSTEM = "SOURCE_WITHOUT_BUILD_SYSTEM"
