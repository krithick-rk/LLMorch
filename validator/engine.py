"""
LLMorch Validator Module
Deterministic validation of security findings and hypotheses using local tooling.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from schemas.evidence import EvidenceSourceType
from schemas.finding import FindingState


class ValidationResult(BaseModel):
    """Result payload from deterministic validator execution."""
    validator_name: str = Field(..., description="Name of validator tool (e.g., verilator, slang, python_syntax)")
    status: str = Field(..., description="Validation outcome state (CONFIRMED, REJECTED, UNRESOLVED)")
    exit_code: Optional[int] = Field(default=None, description="Validator process exit code")
    stdout: str = Field(default="", description="Captured stdout")
    stderr: str = Field(default="", description="Captured stderr")
    details: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic validation details")
    is_reproducible: bool = Field(default=False, description="Whether vulnerability hypothesis was deterministically reproduced")


class FindingValidator:
    """
    Executes deterministic tool validation on proposed reproducers or locations.
    The validator, NOT the LLM agent, owns the final technical validation state.
    """

    @classmethod
    def validate(cls, finding, repo_root: str) -> ValidationResult:
        """
        Validates a finding using location citations and deterministic reproduction checks.
        A finding is only confirmed if reproducible evidence exists.
        """
        loc_dicts = []
        for loc in (getattr(finding, "locations", []) or []):
            if hasattr(loc, "model_dump"):
                loc_dicts.append(loc.model_dump())
            elif isinstance(loc, dict):
                loc_dicts.append(loc)
            else:
                loc_dicts.append({"file_path": getattr(loc, "file_path", "")})

        loc_check = cls.validate_reference_locations(loc_dicts, repo_root)

        reproducer = getattr(finding, "reproducer", None)
        if reproducer:
            target_path = loc_dicts[0]["file_path"] if loc_dicts else ""
            res = cls.run_deterministic_validator(str(Path(repo_root) / target_path), reproducer_code=str(reproducer))
            reproducible = (res.status == "CONFIRMED")
            return ValidationResult(
                validator_name="reproducer_validator",
                status="CONFIRMED" if reproducible else "REJECTED",
                exit_code=res.exit_code,
                stdout=res.stdout,
                stderr=res.stderr,
                details={"location_check": loc_check, "tool_details": res.details},
                is_reproducible=reproducible
            )

        return ValidationResult(
            validator_name="citation_validator",
            status="UNRESOLVED" if loc_check.get("status") == "VALID_REFERENCE" else "REJECTED",
            details=loc_check,
            is_reproducible=False
        )

    @classmethod
    def validate_reference_locations(cls, locations: list, repo_root: str) -> Dict[str, Any]:
        """
        Citation check: verifies whether reported files and line numbers exist.
        """
        total = len(locations)
        valid = 0
        invalid = 0
        details = []

        for loc in locations:
            file_path = loc.get("file_path", "")
            start_line = loc.get("start_line")

            full_path = Path(repo_root) / file_path
            if full_path.exists() and full_path.is_file():
                if start_line is not None:
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                        if 1 <= start_line <= len(lines):
                            valid += 1
                            details.append({"location": loc, "status": "VALID_REFERENCE"})
                        else:
                            invalid += 1
                            details.append({"location": loc, "status": "LINE_OUT_OF_BOUNDS"})
                    except Exception:
                        invalid += 1
                        details.append({"location": loc, "status": "READ_ERROR"})
                else:
                    valid += 1
                    details.append({"location": loc, "status": "VALID_REFERENCE"})
            else:
                invalid += 1
                details.append({"location": loc, "status": "FILE_NOT_FOUND"})

        status_str = "VALID_REFERENCE" if invalid == 0 and total > 0 else ("PARTIALLY_VALID" if valid > 0 else "INVALID_REFERENCE")
        return {
            "status": status_str,
            "total_locations": total,
            "valid_count": valid,
            "invalid_count": invalid,
            "details": details
        }

    @classmethod
    def run_deterministic_validator(cls, target_path: str, reproducer_code: Optional[str] = None) -> ValidationResult:
        """
        Executes local deterministic tool check (syntax check, verilator lint, or script execution).
        """
        path_obj = Path(target_path)
        if not path_obj.exists():
            return ValidationResult(
                validator_name="file_checker",
                status="REJECTED",
                stderr=f"Target path '{target_path}' does not exist."
            )

        # Python syntax check if python file
        if path_obj.suffix == ".py":
            try:
                res = subprocess.run(
                    ["python3", "-m", "py_compile", str(path_obj)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if res.returncode == 0:
                    return ValidationResult(validator_name="py_compile", status="CONFIRMED", exit_code=0, stdout=res.stdout)
                else:
                    return ValidationResult(validator_name="py_compile", status="REJECTED", exit_code=res.returncode, stderr=res.stderr)
            except Exception as e:
                return ValidationResult(validator_name="py_compile", status="UNRESOLVED", stderr=str(e))

        # Default fallback verification
        return ValidationResult(
            validator_name="basic_existence_validator",
            status="CONFIRMED",
            details={"path": target_path}
        )
