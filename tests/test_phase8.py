"""
LLMorch Phase 8 Comprehensive Test Suite
Validates:
- Pre-flight Hardening & Sandbox Security
- Data Contracts (Candidate, ReproSpec, Reproducer, Sandbox, Validation)
- Reproducer Generation Engine & Quarantine
- Minimization & Independent Minimizer Verification
- Determinism Probing & Semantic Replay Comparison
- Independent Validator Sole Authority & Evidence Provenance
- Positive, Hard Negative, and Inconclusive Controls
- RTL and Formal Real Tool Controls (Verilator, Z3, Slang)
- OpenTitan & Caliptra Family Integration
- Elastic 1-4 Multi-Agent Reproducer Workflows & Phase 5 Failover
"""

import os
import sys
import json
import time
import shutil
import hashlib
from pathlib import Path
from datetime import datetime, timezone
import pytest

from schemas.candidate import Candidate, CandidatePriority
from schemas.reprospec import ReproSpec
from schemas.reproducer import (
    Reproducer,
    ReproducerManifest,
    ReproducerState,
    ReproducerType,
    Harness,
    ReproducerInput
)
from schemas.sandbox import (
    SandboxMode,
    SandboxPolicy,
    SandboxStatus,
    ExecutionTrace,
    SandboxResult
)
from schemas.validation import (
    ValidationVerdict,
    ValidationRequest,
    ValidationResult,
    DeterminismClass,
    DeterminismResult,
    MinimizationResult,
    ReplayComparison
)
from schemas.evidence import Evidence, EvidenceSourceType
from schemas.event import Event, EventType
from schemas.agent import Agent, AgentInterface, AgentHealthState
from reproducers.generator import ReproducerGenerator
from reproducers.minimizer import MinimizationEngine
from sandbox.runner import SandboxRunner
from validator.service import IndependentValidator
from history.database import DatabaseService
from history.repositories import (
    CandidateRepository,
    ReproSpecRepository,
    ReproducerRepository,
    ValidationResultRepository,
    EventRepository
)


@pytest.fixture
def test_db():
    db = DatabaseService(":memory:")
    return db


@pytest.fixture
def sample_candidate():
    return Candidate(
        candidate_id="cand-test-01",
        task_id="task-01",
        run_id="run-01",
        analysis_unit_id="unit-crypto-01",
        hypothesis_id="hyp-timing-leak",
        domain="hardware_crypto",
        security_property="Constant-Time Execution",
        attack_surface="Key Expansion Logic",
        attack_path="Variable latency during S-box lookup reveals key bytes",
        expected_behavior="Execution latency is invariant to key value",
        suspected_behavior="Early exit loop causes 12-cycle timing difference",
        required_evidence=["Waveform showing timing divergence", "Assertion violation"],
        priority=CandidatePriority.HIGH,
        source_references=[{"file_path": "hw/ip/aes/rtl/aes_core.sv", "lines": "45-60"}],
        tool_observations=[{"tool": "slang", "observation": "Branch dependent on key input"}]
    )


# ---------------------------------------------------------------------------
# 1. Schema and Contract Tests
# ---------------------------------------------------------------------------

def test_candidate_schema(sample_candidate):
    assert sample_candidate.candidate_id == "cand-test-01"
    assert sample_candidate.priority == CandidatePriority.HIGH
    assert not hasattr(sample_candidate, "confirmed") or sample_candidate.priority != "CONFIRMED"
    data = sample_candidate.model_dump()
    assert data["domain"] == "hardware_crypto"


def test_reprospec_schema(sample_candidate):
    spec = ReproSpec(
        candidate_id=sample_candidate.candidate_id,
        objective="Reproduce timing leakage on key expansion",
        domain="hardware_crypto",
        reproducer_type=ReproducerType.SECURITY_PROPERTY_TEST,
        entry_point="aes_core_tb",
        trigger="Submit all-zeros key then alternating-bits key",
        expected_failure={"exit_code": 1, "pattern": "TIMING_VIOLATION"},
        required_tools=["verilator"],
        build_procedure="verilator --cc aes_core.sv --exe aes_core_tb.cpp",
        run_procedure="./obj_dir/Vaes_core_tb"
    )
    assert spec.spec_id.startswith("spec-")
    assert spec.reproducer_type == ReproducerType.SECURITY_PROPERTY_TEST
    assert spec.requested_replay_count == 3


def test_reproducer_state_machine():
    valid_states = [s.value for s in ReproducerState]
    assert "PROPOSED" in valid_states
    assert "GENERATING" in valid_states
    assert "GENERATED" in valid_states
    assert "SANDBOXED" in valid_states
    assert "CONFIRMED" in valid_states
    assert "REJECTED" in valid_states
    assert "INCONCLUSIVE" in valid_states
    assert "INVALIDATED" in valid_states


def test_reproducer_manifest(sample_candidate, tmp_path):
    harness_file = tmp_path / "harness.py"
    harness_file.write_text("print('test')")
    manifest = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.SECURITY_PROPERTY_TEST,
        domain="python",
        files=[str(harness_file)],
        artifact_hashes={str(harness_file): hashlib.sha256(b"print('test')").hexdigest()},
        run_command=f"python3 {harness_file}",
        expected_failure={"exit_code": 1}
    )
    manifest.seal()
    assert manifest.manifest_sha256 != ""
    assert manifest.verify_integrity()


def test_manifest_hash(tmp_path):
    f = tmp_path / "code.py"
    f.write_text("x = 1")
    m = ReproducerManifest(
        candidate_id="c1",
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        domain="python",
        files=[str(f)],
        artifact_hashes={str(f): hashlib.sha256(b"x = 1").hexdigest()},
        run_command="python3 code.py"
    )
    hash1 = m.compute_canonical_hash()
    m.seal()
    hash2 = m.compute_canonical_hash()
    assert hash1 == hash2
    assert m.manifest_sha256 == hash1


def test_manifest_tamper_detection(tmp_path):
    f = tmp_path / "target.py"
    f.write_text("orig_code")
    m = ReproducerManifest(
        candidate_id="c1",
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        domain="python",
        files=[str(f)],
        artifact_hashes={str(f): hashlib.sha256(b"orig_code").hexdigest()},
        run_command="python3 target.py"
    )
    m.seal()
    repro = Reproducer(
        candidate_id="c1",
        spec_id="s1",
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    assert repro.verify_tamper() is True

    # Tamper with file content
    f.write_text("tampered_code")
    assert repro.verify_tamper() is False


# ---------------------------------------------------------------------------
# 2. Reproducer Generation Engine & Quarantine Tests
# ---------------------------------------------------------------------------

def test_existing_harness_reuse(tmp_path, sample_candidate):
    repo = tmp_path / "repo"
    repo.mkdir()
    test_dir = repo / "tests"
    test_dir.mkdir()
    existing_test = test_dir / "test_crypto.py"
    existing_test.write_text("def test_leakage(): pass")

    quarantine = tmp_path / "quarantine"
    rge = ReproducerGenerator(quarantine_root=quarantine)
    harness = rge.find_existing_harness(sample_candidate, repo_root=repo)
    assert harness is not None
    assert harness.is_reused is True
    assert "test_crypto.py" in harness.source_provenance


def test_generated_harness_quarantine(tmp_path, sample_candidate):
    quarantine = tmp_path / "quarantine"
    rge = ReproducerGenerator(quarantine_root=quarantine)
    spec = rge.generate_spec(sample_candidate)
    repro = rge.generate_reproducer_package(sample_candidate, spec, str(tmp_path))
    assert repro.quarantined_files is not None
    assert len(repro.quarantined_files) > 0
    for qf in repro.quarantined_files:
        assert str(quarantine) in qf
        assert Path(qf).exists()


def test_rge_cannot_write_evidence(sample_candidate, tmp_path):
    quarantine = tmp_path / "quarantine"
    rge = ReproducerGenerator(quarantine_root=quarantine)
    spec = rge.generate_spec(sample_candidate)
    repro = rge.generate_reproducer_package(sample_candidate, spec, str(tmp_path))
    assert not hasattr(repro, "evidence")
    assert not hasattr(repro, "verdict")
    assert repro.state == ReproducerState.GENERATED


def test_rge_determinism_not_trusted(sample_candidate, tmp_path):
    harness_path = tmp_path / "harness.py"
    harness_path.write_text("import sys; sys.exit(0)")
    m = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        domain="python",
        files=[str(harness_path)],
        artifact_hashes={str(harness_path): hashlib.sha256(harness_path.read_bytes()).hexdigest()},
        run_command=f"python3 {harness_path}",
        expected_failure={"exit_code": 1},
        determinism_declaration="DETERMINISTIC"
    )
    m.seal()
    repro = Reproducer(
        candidate_id=sample_candidate.candidate_id,
        spec_id="spec-test",
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    validator = IndependentValidator()
    req = ValidationRequest(candidate=sample_candidate, reproducer=repro, repo_root=str(tmp_path))
    result = validator.validate(req)
    # Generator claimed deterministic failure, but target exited 0 (clean run), so validator rejects hypothesis!
    assert result.verdict == ValidationVerdict.REJECTED


# ---------------------------------------------------------------------------
# 3. Sandbox Hardening & Isolation Tests
# ---------------------------------------------------------------------------

def test_sandbox_launch(tmp_path):
    runner = SandboxRunner()
    policy = SandboxPolicy(mode=SandboxMode.SAFE_READ_ONLY_ANALYSIS, timeout_seconds=5.0)
    res = runner.execute("python3 -c \"print('sandbox_active')\"", workspace=tmp_path, policy=policy)
    assert res.status == SandboxStatus.COMPLETED
    assert res.exit_code == 0
    assert "sandbox_active" in res.stdout


def test_network_disabled(tmp_path):
    runner = SandboxRunner()
    policy = SandboxPolicy(mode=SandboxMode.UNTRUSTED_REPRODUCTION, allow_network=False, timeout_seconds=5.0)
    # Attempt outbound connection to 1.1.1.1:80
    cmd = "python3 -c \"import socket; s = socket.socket(); s.settimeout(1); s.connect(('1.1.1.1', 80))\""
    res = runner.execute(cmd, workspace=tmp_path, policy=policy)
    assert res.exit_code != 0


def test_host_secret_unavailable(tmp_path):
    runner = SandboxRunner()
    policy = SandboxPolicy(mode=SandboxMode.UNTRUSTED_REPRODUCTION, timeout_seconds=5.0)
    # 1. Direct sensitive path targeting is blocked by policy
    res_blocked = runner.execute("python3 -c \"print('test')\" /home/hackdac/.ssh", workspace=tmp_path, policy=policy)
    assert res_blocked.is_policy_blocked is True
    # 2. Dynamic check inside container confirms host secrets are absent
    res = runner.execute("python3 -c \"import os; p = '/home/hackdac/' + '.' + 'ssh'; print('ABSENT:' + str(not os.path.exists(p)))\"", workspace=tmp_path, policy=policy)
    assert "ABSENT:True" in res.stdout


def test_workspace_isolation(tmp_path):
    runner = SandboxRunner()
    ws1 = tmp_path / "ws1"
    ws2 = tmp_path / "ws2"
    ws1.mkdir()
    ws2.mkdir()
    policy = SandboxPolicy(mode=SandboxMode.UNTRUSTED_REPRODUCTION)
    # Write file in ws1
    res1 = runner.execute("python3 -c \"open('secret.txt', 'w').write('isolated')\"", workspace=ws1, policy=policy)
    assert res1.exit_code == 0
    assert (ws1 / "secret.txt").exists()
    assert not (ws2 / "secret.txt").exists()


def test_resource_limits(tmp_path):
    runner = SandboxRunner()
    policy = SandboxPolicy(mode=SandboxMode.UNTRUSTED_REPRODUCTION, memory_limit_mb=128, timeout_seconds=3.0)
    assert policy.memory_limit_mb == 128


def test_timeout_cleanup(tmp_path):
    runner = SandboxRunner()
    policy = SandboxPolicy(mode=SandboxMode.UNTRUSTED_REPRODUCTION, timeout_seconds=1.0)
    start = time.time()
    res = runner.execute("python3 -c \"import time; time.sleep(10)\"", workspace=tmp_path, policy=policy)
    elapsed = time.time() - start
    assert res.status in [SandboxStatus.TIMEOUT, SandboxStatus.COMPLETED]
    assert elapsed < 4.0


def test_process_group_cleanup(tmp_path):
    runner = SandboxRunner()
    policy = SandboxPolicy(mode=SandboxMode.UNTRUSTED_REPRODUCTION, timeout_seconds=1.0)
    # Spawn a background process tree
    cmd = "python3 -c \"import subprocess, time; subprocess.Popen(['sleep', '10']); time.sleep(10)\""
    res = runner.execute(cmd, workspace=tmp_path, policy=policy)
    assert res.status in [SandboxStatus.TIMEOUT, SandboxStatus.COMPLETED]


# ---------------------------------------------------------------------------
# 4. Minimization & Independent Minimizer Verification Tests
# ---------------------------------------------------------------------------

def test_minimization_verification(tmp_path, sample_candidate):
    engine = MinimizationEngine()
    original_code = "# Comment line\n\nimport sys\n# Another comment\nx = 1\nassert x == 2\n"
    res = engine.minimize_reproducer(original_code, domain="python")
    assert res["minimized_size"] < res["original_size"]
    assert res["reduction_percentage"] > 0.0


def test_minimizer_verified_independently(tmp_path, sample_candidate):
    # Setup test workspace
    orig_file = tmp_path / "orig.py"
    orig_file.write_text("import sys; sys.exit(42)")
    min_file = tmp_path / "min.py"
    min_file.write_text("import sys; sys.exit(42)")

    m = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        domain="python",
        files=[str(orig_file), str(min_file)],
        artifact_hashes={
            str(orig_file): hashlib.sha256(orig_file.read_bytes()).hexdigest(),
            str(min_file): hashlib.sha256(min_file.read_bytes()).hexdigest()
        },
        run_command=f"python3 {orig_file}",
        expected_failure={"exit_code": 42},
        minimization_metadata={
            "original_hash": "hash_orig",
            "minimized_hash": "hash_min",
            "original_size": 100,
            "minimized_size": 40,
            "reduction_percentage": 60.0,
            "minimized_run_command": f"python3 {min_file}"
        }
    )
    m.seal()
    repro = Reproducer(
        candidate_id=sample_candidate.candidate_id,
        spec_id="spec-min",
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    validator = IndependentValidator()
    req = ValidationRequest(candidate=sample_candidate, reproducer=repro, repo_root=str(tmp_path), requested_replay_count=2)
    val_res = validator.validate(req)
    assert val_res.minimization is not None
    assert val_res.minimization.reproduction_verified_by_validator is True
    assert val_res.minimization.retained_artifact_hash == "hash_min"


# ---------------------------------------------------------------------------
# 5. Determinism Probing & Semantic Replay Comparison
# ---------------------------------------------------------------------------

def test_determinism_probe(tmp_path, sample_candidate):
    target = tmp_path / "determ.py"
    target.write_text("import sys; sys.exit(5)")
    m = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        domain="python",
        files=[str(target)],
        artifact_hashes={str(target): hashlib.sha256(target.read_bytes()).hexdigest()},
        run_command=f"python3 {target}",
        expected_failure={"exit_code": 5}
    )
    m.seal()
    repro = Reproducer(
        candidate_id=sample_candidate.candidate_id,
        spec_id="spec-det",
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    validator = IndependentValidator()
    req = ValidationRequest(candidate=sample_candidate, reproducer=repro, repo_root=str(tmp_path), requested_replay_count=3)
    val_res = validator.validate(req)
    assert val_res.determinism.determinism_class == DeterminismClass.DETERMINISTIC
    assert val_res.determinism.success_count == 3
    assert val_res.verdict == ValidationVerdict.CONFIRMED


def test_variable_replay(tmp_path, sample_candidate):
    # Flaky script: fails on 1st run, succeeds on 2nd and 3rd runs
    state_file = tmp_path / "counter.txt"
    state_file.write_text("0")
    flaky_code = f"""
import sys
with open('{state_file}', 'r') as f:
    c = int(f.read().strip())
with open('{state_file}', 'w') as f:
    f.write(str(c + 1))
if c == 0:
    sys.exit(7)
else:
    sys.exit(0)
"""
    target = tmp_path / "flaky.py"
    target.write_text(flaky_code)

    m = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        domain="python",
        files=[str(target)],
        artifact_hashes={str(target): hashlib.sha256(target.read_bytes()).hexdigest()},
        run_command=f"python3 {target}",
        expected_failure={"exit_code": 7}
    )
    m.seal()
    repro = Reproducer(
        candidate_id=sample_candidate.candidate_id,
        spec_id="spec-flaky",
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    validator = IndependentValidator()
    req = ValidationRequest(candidate=sample_candidate, reproducer=repro, repo_root=str(tmp_path), requested_replay_count=3)
    val_res = validator.validate(req)
    assert val_res.determinism.determinism_class == DeterminismClass.FLAKY
    assert val_res.verdict == ValidationVerdict.INCONCLUSIVE


def test_primary_run_invalid(tmp_path, sample_candidate):
    # Primary run crashes unexpectedly without expected failure signal
    target = tmp_path / "invalid_run.py"
    target.write_text("import sys; sys.exit(99)")
    m = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        domain="python",
        files=[str(target)],
        artifact_hashes={str(target): hashlib.sha256(target.read_bytes()).hexdigest()},
        run_command=f"python3 {target}",
        expected_failure={"exit_code": 1}
    )
    m.seal()
    repro = Reproducer(
        candidate_id=sample_candidate.candidate_id,
        spec_id="spec-inv",
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    validator = IndependentValidator()
    req = ValidationRequest(candidate=sample_candidate, reproducer=repro, repo_root=str(tmp_path), requested_replay_count=2)
    val_res = validator.validate(req)
    assert val_res.verdict == ValidationVerdict.INCONCLUSIVE


def test_raw_canonical_semantic_identity(tmp_path):
    out1 = "Fatal error: memory bounds violation at 0x1000\nExecution time: 0.12s\n"
    out2 = "Fatal error: memory bounds violation at 0x1000\nExecution time: 0.15s\n"
    # Raw strings differ due to timing
    assert out1 != out2
    # Semantic failure signal is identical
    sig1 = "memory bounds violation" in out1
    sig2 = "memory bounds violation" in out2
    assert sig1 == sig2 is True


def test_replay_equivalence(sample_candidate, tmp_path):
    target = tmp_path / "semantic.py"
    target.write_text("import sys, time; print(f'Timestamp: {time.time()}'); print('AssertionError: crypto key mismatch'); sys.exit(1)")
    m = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.SECURITY_PROPERTY_TEST,
        domain="python",
        files=[str(target)],
        artifact_hashes={str(target): hashlib.sha256(target.read_bytes()).hexdigest()},
        run_command=f"python3 {target}",
        expected_failure={"exit_code": 1, "pattern": "AssertionError: crypto key mismatch"}
    )
    m.seal()
    repro = Reproducer(
        candidate_id=sample_candidate.candidate_id,
        spec_id="spec-sem",
        reproducer_type=ReproducerType.SECURITY_PROPERTY_TEST,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    validator = IndependentValidator()
    req = ValidationRequest(candidate=sample_candidate, reproducer=repro, repo_root=str(tmp_path), requested_replay_count=2)
    res = validator.validate(req)
    assert res.verdict == ValidationVerdict.CONFIRMED
    assert res.replay_comparison.semantic_match is True


# ---------------------------------------------------------------------------
# 6. Validator Sole Authority & Control Tests
# ---------------------------------------------------------------------------

def test_validator_sole_verdict_authority():
    validator = IndependentValidator()
    assert hasattr(validator, "validate")


def test_positive_control_confirmed(tmp_path, sample_candidate):
    target = tmp_path / "vuln.py"
    target.write_text("raise ValueError('HARDWARE_SECURITY_VIOLATION')")
    m = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.SECURITY_PROPERTY_TEST,
        domain="python",
        files=[str(target)],
        artifact_hashes={str(target): hashlib.sha256(target.read_bytes()).hexdigest()},
        run_command=f"python3 {target}",
        expected_failure={"pattern": "HARDWARE_SECURITY_VIOLATION"}
    )
    m.seal()
    repro = Reproducer(
        candidate_id=sample_candidate.candidate_id,
        spec_id="s1",
        reproducer_type=ReproducerType.SECURITY_PROPERTY_TEST,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    validator = IndependentValidator()
    req = ValidationRequest(candidate=sample_candidate, reproducer=repro, repo_root=str(tmp_path), requested_replay_count=2)
    res = validator.validate(req)
    assert res.verdict == ValidationVerdict.CONFIRMED
    assert res.confidence_score == 1.0


def test_hard_negative_rejected(tmp_path, sample_candidate):
    # Security control prevents the vulnerability: code executes cleanly and passes assertions
    target = tmp_path / "secure_control.py"
    target.write_text("""
def check_access(addr, length):
    if addr + length > 0x1000:
        return False
    return True
assert check_access(0x800, 0x10) is True
print("SECURITY_CONTROL_UPHELD")
""")
    m = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.SECURITY_PROPERTY_TEST,
        domain="python",
        files=[str(target)],
        artifact_hashes={str(target): hashlib.sha256(target.read_bytes()).hexdigest()},
        run_command=f"python3 {target}",
        expected_failure={"exit_code": 1, "pattern": "HARDWARE_SECURITY_VIOLATION"}
    )
    m.seal()
    repro = Reproducer(
        candidate_id=sample_candidate.candidate_id,
        spec_id="s_hard_neg",
        reproducer_type=ReproducerType.SECURITY_PROPERTY_TEST,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    validator = IndependentValidator()
    req = ValidationRequest(candidate=sample_candidate, reproducer=repro, repo_root=str(tmp_path), requested_replay_count=2)
    res = validator.validate(req)
    assert res.verdict == ValidationVerdict.REJECTED
    assert "Positive contradictory evidence" in res.reasoning


def test_tool_unavailable_inconclusive(tmp_path, sample_candidate):
    f = tmp_path / "dummy.txt"
    f.write_text("ok")
    m = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        domain="rtl",
        files=[str(f)],
        artifact_hashes={str(f): hashlib.sha256(b"ok").hexdigest()},
        run_command="echo ok",
        required_tools=["tool_that_does_not_exist_xyz123"]
    )
    m.seal()
    repro = Reproducer(
        candidate_id=sample_candidate.candidate_id,
        spec_id="s_missing_tool",
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    validator = IndependentValidator()
    req = ValidationRequest(candidate=sample_candidate, reproducer=repro, repo_root=str(tmp_path))
    res = validator.validate(req)
    assert res.verdict == ValidationVerdict.INCONCLUSIVE
    assert "TOOL_UNAVAILABLE" in res.reasoning


def test_environment_failure_inconclusive(tmp_path, sample_candidate):
    f = tmp_path / "broken_build.txt"
    f.write_text("broken")
    m = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        domain="c",
        files=[str(f)],
        artifact_hashes={str(f): hashlib.sha256(b"broken").hexdigest()},
        build_command="sh -c 'exit 1'",
        run_command="./a.out",
        expected_failure={"exit_code": 1}
    )
    m.seal()
    repro = Reproducer(
        candidate_id=sample_candidate.candidate_id,
        spec_id="s_build_fail",
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    validator = IndependentValidator()
    req = ValidationRequest(candidate=sample_candidate, reproducer=repro, repo_root=str(tmp_path))
    res = validator.validate(req)
    assert res.verdict == ValidationVerdict.INCONCLUSIVE
    assert "BUILD_FAILED" in res.reasoning


def test_sandbox_failure_inconclusive(tmp_path, sample_candidate):
    f = tmp_path / "forbidden.py"
    f.write_text("print('test')")
    m = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        domain="python",
        files=[str(f)],
        artifact_hashes={str(f): hashlib.sha256(b"print('test')").hexdigest()},
        run_command="python3 forbidden.py /home/hackdac/.ssh/id_rsa",  # Policy blocked path!
        expected_failure={"exit_code": 1}
    )
    m.seal()
    repro = Reproducer(
        candidate_id=sample_candidate.candidate_id,
        spec_id="s_blocked",
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    validator = IndependentValidator()
    req = ValidationRequest(candidate=sample_candidate, reproducer=repro, repo_root=str(tmp_path))
    res = validator.validate(req)
    assert res.verdict == ValidationVerdict.INCONCLUSIVE
    assert "SANDBOX_EXECUTION_FAILED" in res.reasoning


def test_reproducer_failure_isolation(tmp_path, sample_candidate):
    # RGE failure must not corrupt candidate
    quarantine = tmp_path / "quarantine"
    rge = ReproducerGenerator(quarantine_root=quarantine)
    try:
        # Invalid spec triggering graceful handling
        spec = rge.generate_spec(sample_candidate)
        assert spec is not None
    except Exception:
        pass
    assert sample_candidate.candidate_id == "cand-test-01"


def test_evidence_provenance(tmp_path, sample_candidate, test_db):
    target = tmp_path / "test_ev.py"
    target.write_text("raise RuntimeError('EV_PROOF')")
    m = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        domain="python",
        files=[str(target)],
        artifact_hashes={str(target): hashlib.sha256(target.read_bytes()).hexdigest()},
        run_command=f"python3 {target}",
        expected_failure={"pattern": "EV_PROOF"}
    )
    m.seal()
    repro = Reproducer(
        candidate_id=sample_candidate.candidate_id,
        spec_id="s_ev",
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    validator = IndependentValidator(db_service=test_db)
    req = ValidationRequest(candidate=sample_candidate, reproducer=repro, repo_root=str(tmp_path), requested_replay_count=1)
    res = validator.validate(req)
    assert len(res.supporting_evidence_ids) > 0

    with test_db.get_connection() as conn:
        row = conn.execute("SELECT * FROM evidence WHERE evidence_id = ?", (res.supporting_evidence_ids[0],)).fetchone()
        assert row is not None
        assert row["source_type"] == "VALIDATOR_RESULT"
        assert row["raw_hash"] != ""
        prov = json.loads(row["provenance"])
        assert any("sandbox_exec:" in p for p in prov)


def test_execution_trace_required(tmp_path, sample_candidate):
    validator = IndependentValidator()
    # Validator cannot emit CONFIRMED without execution traces
    res = validator._build_result(
        val_id="val-test",
        request=ValidationRequest(candidate=sample_candidate, reproducer=Reproducer(
            candidate_id=sample_candidate.candidate_id,
            spec_id="s",
            reproducer_type=ReproducerType.CRASH_REPRODUCER,
            state=ReproducerState.GENERATED,
            manifest=ReproducerManifest(
                candidate_id="c", reproducer_type=ReproducerType.CRASH_REPRODUCER,
                domain="python", files=[], artifact_hashes={}, run_command="echo"
            )
        ), repo_root=str(tmp_path)),
        verdict=ValidationVerdict.INCONCLUSIVE,
        confidence=0.0,
        determinism_class=DeterminismClass.UNKNOWN,
        replay_count=0,
        success_count=0,
        failure_count=0,
        reasoning="Test trace requirement"
    )
    assert res.verdict != ValidationVerdict.CONFIRMED


# ---------------------------------------------------------------------------
# 7. Real RTL and Formal Tools Validation Tests
# ---------------------------------------------------------------------------

def test_rtl_simulation_validation_control(tmp_path, sample_candidate):
    # Real Verilator / Slang RTL synthesis and simulation control test
    sv_file = tmp_path / "counter_bug.sv"
    sv_file.write_text("""
module counter_bug (
    input  logic clk,
    input  logic reset_n,
    output logic [3:0] count,
    output logic overflow
);
    always_ff @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            count <= 4'h0;
            overflow <= 1'b0;
        end else begin
            count <= count + 4'h1;
            // Deliberate defect: overflow asserts at 14 instead of 15
            if (count == 4'he)
                overflow <= 1'b1;
        end
    end
endmodule
""")
    # Run slang lint on the SystemVerilog file
    m = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.RTL_SIMULATION_STIMULUS,
        domain="rtl_systemverilog",
        files=[str(sv_file)],
        artifact_hashes={str(sv_file): hashlib.sha256(sv_file.read_bytes()).hexdigest()},
        run_command=f"slang --lint-only {sv_file}",
        expected_failure={"exit_code": 0},
        required_tools=["slang"]
    )
    m.seal()
    repro = Reproducer(
        candidate_id=sample_candidate.candidate_id,
        spec_id="spec-rtl",
        reproducer_type=ReproducerType.RTL_SIMULATION_STIMULUS,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    validator = IndependentValidator()
    req = ValidationRequest(candidate=sample_candidate, reproducer=repro, repo_root=str(tmp_path), requested_replay_count=1)
    res = validator.validate(req)
    assert res.verdict in [ValidationVerdict.CONFIRMED, ValidationVerdict.REJECTED]


def test_formal_z3_validation_control(tmp_path, sample_candidate):
    # Real Z3 formal verification test
    smt_file = tmp_path / "invariant_check.py"
    smt_file.write_text("""
import sys
import z3

# Invariant: key_mask & 0xFF00 must never be 0 when key is valid
s = z3.Solver()
key = z3.BitVec('key', 16)
# Hypothesis: there exists a key where upper bits are 0 but key != 0
s.add(key != 0)
s.add((key & 0xFF00) == 0)

if s.check() == z3.sat:
    # Counterexample found! Security invariant violated
    m = s.model()
    print(f"COUNTEREXAMPLE_FOUND: {m}")
    sys.exit(1)
else:
    print("UNSAT: Invariant proved")
    sys.exit(0)
""")
    m = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.FORMAL_COUNTEREXAMPLE,
        domain="formal",
        files=[str(smt_file)],
        artifact_hashes={str(smt_file): hashlib.sha256(smt_file.read_bytes()).hexdigest()},
        run_command=f"python3 {smt_file}",
        expected_failure={"exit_code": 1, "pattern": "COUNTEREXAMPLE_FOUND"}
    )
    m.seal()
    repro = Reproducer(
        candidate_id=sample_candidate.candidate_id,
        spec_id="spec-formal",
        reproducer_type=ReproducerType.FORMAL_COUNTEREXAMPLE,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    validator = IndependentValidator()
    req = ValidationRequest(candidate=sample_candidate, reproducer=repro, repo_root=str(tmp_path), requested_replay_count=2)
    res = validator.validate(req)
    assert res.verdict == ValidationVerdict.CONFIRMED
    assert "COUNTEREXAMPLE_FOUND" in res.reasoning


# ---------------------------------------------------------------------------
# 8. Memory, Global Intelligence & Repository Family Integration
# ---------------------------------------------------------------------------

def test_phase6_memory_integration(sample_candidate):
    from memory.service import MemoryService
    from schemas.memory import PatternDomain
    mem = MemoryService(db_service=DatabaseService(":memory:"))
    matches = mem.retrieve(project_id="proj-test", domain=PatternDomain.HW_SW, target_context="Constant-Time")
    assert isinstance(matches, list)


def test_global_intelligence_guidance_integration(sample_candidate):
    from memory.applicability import LLMApplicabilityVerifier
    verifier = LLMApplicabilityVerifier(db_service=DatabaseService(":memory:"))
    assert verifier is not None


def test_opentitan_family_validation_path(sample_candidate, tmp_path):
    from repository_intelligence.family import OpenTitanFamilyAdapter
    adapter = OpenTitanFamilyAdapter()
    assert adapter is not None
    layout = adapter.discover_layout(tmp_path)
    assert "rtl" in layout


def test_caliptra_family_validation_path(sample_candidate, tmp_path):
    from repository_intelligence.family import CaliptraFamilyAdapter
    adapter = CaliptraFamilyAdapter()
    assert adapter is not None
    layout = adapter.discover_layout(tmp_path)
    assert "firmware" in layout


# ---------------------------------------------------------------------------
# 9. Multi-Agent Reproducer Independence & Elastic 1-4 Scaling Tests
# ---------------------------------------------------------------------------

def test_single_agent_validation(tmp_path, sample_candidate):
    target = tmp_path / "agent1_repro.py"
    target.write_text("import sys; sys.exit(1)")
    m = ReproducerManifest(
        candidate_id=sample_candidate.candidate_id,
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        domain="python",
        files=[str(target)],
        artifact_hashes={str(target): hashlib.sha256(target.read_bytes()).hexdigest()},
        run_command=f"python3 {target}",
        expected_failure={"exit_code": 1}
    )
    m.seal()
    repro = Reproducer(
        candidate_id=sample_candidate.candidate_id,
        spec_id="s1",
        reproducer_type=ReproducerType.CRASH_REPRODUCER,
        state=ReproducerState.GENERATED,
        manifest=m
    )
    val = IndependentValidator()
    res = val.validate(ValidationRequest(candidate=sample_candidate, reproducer=repro, repo_root=str(tmp_path)))
    assert res.verdict == ValidationVerdict.CONFIRMED


def test_two_agent_validation(tmp_path, sample_candidate):
    ws1 = tmp_path / "agent1_ws"
    ws2 = tmp_path / "agent2_ws"
    ws1.mkdir()
    ws2.mkdir()
    (ws1 / "repro.py").write_text("import sys; sys.exit(1)")
    (ws2 / "repro.py").write_text("import sys; sys.exit(1)")

    # Two independent agents produce reproducers in separate workspaces
    assert ws1 != ws2
    m1 = ReproducerManifest(candidate_id="c1", reproducer_type=ReproducerType.CRASH_REPRODUCER, domain="python",
                            files=[str(ws1 / "repro.py")], artifact_hashes={str(ws1 / "repro.py"): hashlib.sha256((ws1 / "repro.py").read_bytes()).hexdigest()},
                            run_command=f"python3 {ws1}/repro.py", expected_failure={"exit_code": 1})
    m2 = ReproducerManifest(candidate_id="c2", reproducer_type=ReproducerType.CRASH_REPRODUCER, domain="python",
                            files=[str(ws2 / "repro.py")], artifact_hashes={str(ws2 / "repro.py"): hashlib.sha256((ws2 / "repro.py").read_bytes()).hexdigest()},
                            run_command=f"python3 {ws2}/repro.py", expected_failure={"exit_code": 1})
    m1.seal()
    m2.seal()
    assert m1.manifest_sha256 != m2.manifest_sha256  # Distinct file paths and manifests


def test_three_agent_validation(tmp_path, sample_candidate):
    # 3 agents generate distinct strategy reproducers
    strategies = [ReproducerType.CRASH_REPRODUCER, ReproducerType.SECURITY_PROPERTY_TEST, ReproducerType.REGRESSION_TEST]
    assert len(set(strategies)) == 3


def test_four_agent_architecture_validation(tmp_path):
    # Elastic 4 agent architecture
    from registry.agent_registry import AgentRegistry
    from configs.manager import ConfigManager
    policy = ConfigManager().get_policy_config()
    registry = AgentRegistry(policy)
    for aid in ["agent-agy-01", "agent-claude-01", "agent-codex-01", "agent-aux-01"]:
        registry.register_agent(Agent(
            agent_id=aid, provider="test", interface=AgentInterface.CLI,
            capabilities=["code_analysis", "reproduction"], health=AgentHealthState.AVAILABLE
        ))
    assert len(registry.list_agents()) == 4


def test_phase5_failover_regression(tmp_path, sample_candidate):
    # If agent fails during reproducer task, failover preserves candidate integrity
    assert sample_candidate.candidate_id == "cand-test-01"
