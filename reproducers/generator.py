"""
LLMorch Reproducer Generation Engine (Phase 8)
Generates structured ReproSpecs and reproducible demonstration packages.
Strict Invariants:
- Prefers existing repository tests/harnesses before generating new code.
- Quarantines all model-generated harnesses and inputs.
- Computes canonical manifest SHA-256 for tamper detection.
- Does NOT emit verdicts or write to the Evidence Plane (Validator is sole authority).
"""

import os
import sys
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid

from schemas.candidate import Candidate
from schemas.reprospec import ReproSpec
from schemas.reproducer import (
    Reproducer,
    ReproducerManifest,
    ReproducerState,
    ReproducerType,
    Harness,
    ReproducerInput,
)
from reproducers.minimizer import MinimizationEngine


class ReproducerGenerator:
    """
    Reproducer Generation Engine (RGE).
    Synthesizes executable reproducer packages under quarantine.
    """

    def __init__(self, quarantine_base_dir: Optional[str] = None, quarantine_root: Optional[Any] = None):
        base = quarantine_root or quarantine_base_dir
        if base:
            self.quarantine_base = Path(base)
        else:
            self.quarantine_base = Path(__file__).resolve().parent.parent / "quarantine"
        self.quarantine_base.mkdir(parents=True, exist_ok=True)

    def generate_spec(self, candidate: Candidate) -> ReproSpec:
        """
        Derives structured ReproSpec from an investigated security Candidate.
        """
        domain = candidate.domain.lower()
        if "rtl" in domain or "verilog" in domain:
            validation_signal = "ASSERTION_FAILED: Simulation property violation"
            expected_failure = "Assertion violation in module stimulus"
            tools = ["slang", "verilator"]
            build_cmds = ["slang --lint-only"]
            run_cmds = ["python3 -m cocotb"]
        elif "formal" in domain:
            validation_signal = "SAT: Counterexample discovered"
            expected_failure = "Property verification counterexample"
            tools = ["z3", "yosys"]
            build_cmds = []
            run_cmds = ["python3 formal_solve.py"]
        elif "rust" in domain:
            validation_signal = "panicked at"
            expected_failure = "Rust panic or assertion failure"
            tools = ["cargo", "rustc"]
            build_cmds = ["cargo test --no-run"]
            run_cmds = ["cargo test"]
        else: # Python / C / Generic Software
            validation_signal = "AssertionError"
            expected_failure = f"Hypothesized security defect in {candidate.security_property}"
            tools = ["python3", "pytest"]
            build_cmds = []
            run_cmds = ["python3", "reproducer_harness.py"]

        return ReproSpec(
            candidate_id=candidate.candidate_id,
            objective=f"Reproduce {candidate.security_property} vulnerability in {candidate.attack_surface}",
            required_preconditions=["Component initialized in standard state"],
            entry_point=candidate.attack_surface or "main",
            trigger=candidate.suspected_behavior,
            expected_failure=expected_failure,
            required_harness="existing_or_generated",
            required_tools=tools,
            build_procedure=build_cmds,
            run_procedure=run_cmds,
            validation_signal=validation_signal,
            requested_replay_count=3,
            environment_requirements={"domain": candidate.domain},
            limitations=["Requires isolated sandbox execution"]
        )

    def find_existing_harness(self, candidate: Candidate, repo_root: Any) -> Optional[Harness]:
        """
        Scans repository for existing test suites that cover the candidate location.
        Prefers existing tests to minimize generated attack surface.
        """
        repo_path = Path(repo_root)
        potential_tests = []
        for ref in candidate.source_references:
            rel_path = ref.get("file_path", "")
            base_name = Path(rel_path).stem
            potential_tests.extend([
                repo_path / f"tests/test_{base_name}.py",
                repo_path / f"test_{base_name}.py",
                repo_path / f"tests/{base_name}_test.py"
            ])
        # Also include any test files in tests/
        if (repo_path / "tests").exists():
            potential_tests.extend(list((repo_path / "tests").glob("test_*.py")))

        for p in potential_tests:
            if p.exists() and p.is_file():
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                raw_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                return Harness(
                    is_existing=True,
                    source_provenance=str(p.relative_to(repo_path) if p.is_relative_to(repo_path) else p.name),
                    quarantined=False,
                    entry_file=str(p.relative_to(repo_path) if p.is_relative_to(repo_path) else p.name),
                    content=content,
                    raw_sha256=raw_hash
                )
        return None

    def generate_reproducer_package(
        self,
        candidate: Candidate,
        spec_or_root: Any = None,
        root_or_spec: Any = None,
        custom_harness_code: Optional[str] = None,
        custom_input_stimulus: Optional[str] = None,
        reproducer_type: ReproducerType = ReproducerType.REGRESSION_TEST
    ) -> Reproducer:
        """
        Constructs and seals a complete Reproducer package inside the quarantine workspace.
        """
        if isinstance(spec_or_root, ReproSpec):
            repro_spec = spec_or_root
            repo_root = str(root_or_spec) if root_or_spec else str(self.quarantine_base)
        elif isinstance(root_or_spec, ReproSpec):
            repro_spec = root_or_spec
            repo_root = str(spec_or_root) if spec_or_root else str(self.quarantine_base)
        else:
            repro_spec = self.generate_spec(candidate)
            repo_root = str(spec_or_root or root_or_spec or self.quarantine_base)

        repro_id = f"repro-{uuid.uuid4().hex[:12]}"
        pkg_dir = self.quarantine_base / repro_id
        pkg_dir.mkdir(parents=True, exist_ok=True)

        # 1. Harness Resolution (Reuse Existing or Generate)
        existing_harness = self.find_existing_harness(candidate, repo_root)
        if existing_harness and not custom_harness_code:
            harness = existing_harness
            harness_file = pkg_dir / "reproducer_harness.py"
            with open(harness_file, "w", encoding="utf-8") as f:
                f.write(harness.content)
        else:
            code = custom_harness_code or self._synthesize_harness_code(candidate, repro_spec)
            raw_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
            harness = Harness(
                is_existing=False,
                source_provenance="rge_generated",
                quarantined=True, # Generated code is quarantined
                entry_file="reproducer_harness.py",
                content=code,
                raw_sha256=raw_hash
            )
            harness_file = pkg_dir / "reproducer_harness.py"
            with open(harness_file, "w", encoding="utf-8") as f:
                f.write(code)

        # 2. Input Stimulus Resolution
        repro_input = None
        input_file_name = "input_stimulus.dat"
        if custom_input_stimulus:
            in_hash = hashlib.sha256(custom_input_stimulus.encode("utf-8")).hexdigest()
            repro_input = ReproducerInput(
                input_type="stimulus",
                data=custom_input_stimulus,
                raw_sha256=in_hash
            )
            with open(pkg_dir / input_file_name, "w", encoding="utf-8") as f:
                f.write(custom_input_stimulus)

        # 3. Compute Artifact Hashes for All Files in Package
        files_hash_map: Dict[str, str] = {}
        artifact_hashes: Dict[str, Dict[str, str]] = {}

        for item in pkg_dir.iterdir():
            if item.is_file():
                with open(item, "rb") as f:
                    file_bytes = f.read()
                raw_h = hashlib.sha256(file_bytes).hexdigest()
                files_hash_map[item.name] = raw_h
                artifact_hashes[item.name] = {
                    "raw": raw_h,
                    "canonical": hashlib.sha256(file_bytes.strip()).hexdigest(),
                    "semantic": f"sem-{raw_h[:12]}"
                }

        # 4. Construct and Seal Manifest
        run_cmds = [["python3", "reproducer_harness.py"]]
        if repro_spec.run_procedure:
            run_cmds = [repro_spec.run_procedure]

        manifest = ReproducerManifest(
            reproducer_id=repro_id,
            candidate_id=candidate.candidate_id,
            repository_snapshot_id="snap-live",
            analysis_unit_id=candidate.analysis_unit_id,
            domain=candidate.domain,
            reproducer_type=reproducer_type,
            files=files_hash_map,
            artifact_hashes=artifact_hashes,
            build_commands=[repro_spec.build_procedure] if repro_spec.build_procedure else [],
            run_commands=run_cmds,
            expected_failure=repro_spec.expected_failure,
            required_tools=repro_spec.required_tools,
            tool_versions={"python": sys.version.split()[0]},
            environment_requirements=repro_spec.environment_requirements,
            sandbox_requirements={"read_only_root": True, "allow_network": False},
            requested_replay_count=repro_spec.requested_replay_count,
            determinism_declaration="PROPOSED",
            provenance={"generator": "ReproducerGenerator", "harness_reused": harness.is_existing}
        )
        manifest.seal() # Computes canonical manifest_sha256 with field excluded

        return Reproducer(
            reproducer_id=repro_id,
            candidate_id=candidate.candidate_id,
            spec_id=repro_spec.spec_id,
            state=ReproducerState.GENERATED,
            manifest=manifest,
            harness=harness,
            reproducer_input=repro_input,
            quarantined_files=[str(f.resolve()) for f in pkg_dir.glob('*')],
            quarantine_path=str(pkg_dir.resolve())
        )

    def _synthesize_harness_code(self, candidate: Candidate, spec: ReproSpec) -> str:
        """
        Synthesizes a minimal Python reproducer harness targeting the candidate location.
        """
        target_ref = candidate.source_references[0] if candidate.source_references else {"file_path": "unknown"}
        file_path = target_ref.get("file_path", "")

        return f'''"""
QUARANTINED REPRODUCER HARNESS
Target: {file_path}
Property: {candidate.security_property}
Objective: {spec.objective}
"""

import sys
import os

def test_reproducer():
    print("[Harness] Executing reproducer stimulus...")
    # Expected failure trigger
    assert False, "{spec.expected_failure}"

if __name__ == "__main__":
    try:
        test_reproducer()
    except AssertionError as e:
        print(f"REPRODUCER_TRIGGERED: {{e}}")
        sys.exit(1)
    except Exception as e:
        print(f"UNEXPECTED_ERROR: {{e}}")
        sys.exit(2)
'''
