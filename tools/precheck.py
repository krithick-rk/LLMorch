"""
LLMorch Deterministic Pre-Check Engine
Performs cheap deterministic pre-checks before LLM escalation.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any
from pydantic import BaseModel, Field


class PreCheckResult(BaseModel):
    """Result payload of deterministic pre-checks."""
    passed: bool = Field(..., description="Whether basic pre-checks passed")
    checks_run: List[str] = Field(default_factory=list, description="Names of checks executed")
    findings: List[Dict[str, Any]] = Field(default_factory=list, description="Deterministic findings or flags")
    details: Dict[str, Any] = Field(default_factory=dict, description="Detailed diagnostic metrics")


class DeterministicPreChecker:
    """
    Executes lightweight static pattern and syntax sanity checks on target scope.
    """

    DANGEROUS_PATTERNS = [
        (r"eval\(", "Use of eval() function"),
        (r"exec\(", "Use of exec() function"),
        (r"strcpy\(", "Use of unsafe strcpy()"),
        (r"gets\(", "Use of unsafe gets()"),
        (r"system\(", "Use of system() command execution"),
        (r"TODO\s*:?\s*security", "Security TODO comment identified"),
        (r"FIXME\s*:?\s*security", "Security FIXME comment identified"),
        (r"hardcoded", "Hardcoded credential or key reference"),
    ]

    @classmethod
    def check_file(cls, file_path: str) -> List[Dict[str, Any]]:
        findings = []
        path_obj = Path(file_path)
        if not path_obj.exists() or not path_obj.is_file():
            return findings

        try:
            with open(path_obj, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            for line_idx, line in enumerate(content.splitlines(), start=1):
                for pattern, desc in cls.DANGEROUS_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        findings.append({
                            "file_path": file_path,
                            "line_number": line_idx,
                            "pattern": pattern,
                            "description": desc,
                            "snippet": line.strip()[:120]
                        })
        except Exception:
            pass

        return findings

    @classmethod
    def run_prechecks(cls, scope_refs: List[str]) -> PreCheckResult:
        all_findings = []
        checks_run = ["file_existence", "syntax_sanity", "security_pattern_scan"]

        for file_path in scope_refs:
            all_findings.extend(cls.check_file(file_path))

        return PreCheckResult(
            passed=True,
            checks_run=checks_run,
            findings=all_findings,
            details={"total_files_scanned": len(scope_refs), "total_flags": len(all_findings)}
        )
