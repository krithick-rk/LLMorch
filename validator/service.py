"""
LLMorch Validator Service (Phase 8 Independent Validation Engine)
Sole authority for final finding state (CONFIRMED, REJECTED, INCONCLUSIVE).
Independently verifies reproducer manifests, conducts sandbox executions,
probes determinism via multi-replay, verifies minimization, and records
evidence through the Evidence Plane.
"""

import os
import re
import json
import uuid
import shutil
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path

from schemas.candidate import Candidate
from schemas.reproducer import Reproducer, ReproducerState
from schemas.sandbox import SandboxMode, SandboxPolicy, ExecutionTrace
from schemas.validation import (
    ValidationVerdict,
    ValidationRequest,
    ValidationResult,
    DeterminismClass,
    DeterminismResult,
    MinimizationResult,
    ReplayComparison,
    EnvironmentManifest
)
from schemas.evidence import Evidence, EvidenceSourceType
from schemas.event import Event, EventType
from sandbox.runner import SandboxRunner


class IndependentValidator:
    """
    Phase 8 Independent Validation Engine.
    Enforces strict architectural separation:
    - LLM / RGE proposals are untrusted.
    - Validator independently inspects, executes in Sandbox, replays, and issues verdicts.
    """

    def __init__(self, db_service=None, event_repo=None):
        self.db = db_service
        self.event_repo = event_repo
        self.sandbox_runner = SandboxRunner()

    def _record_event(self, event_type: EventType, actor: str, payload: Dict[str, Any], run_id: Optional[str] = None):
        """Emits structured audit event if event repository is available."""
        if self.event_repo:
            try:
                event = Event(
                    event_type=event_type,
                    actor=actor,
                    run_id=run_id,
                    payload=payload
                )
                self.event_repo.save(event)
            except Exception:
                pass

    def validate(self, request: ValidationRequest) -> ValidationResult:
        """
        Executes end-to-end independent validation on a candidate reproducer package.
        """
        val_id = f"val-{uuid.uuid4().hex[:12]}"
        candidate = request.candidate
        reproducer = request.reproducer
        manifest = reproducer.manifest

        self._record_event(
            EventType.VALIDATION_STARTED,
            actor="IndependentValidator",
            payload={"validation_id": val_id, "candidate_id": candidate.candidate_id, "reproducer_id": reproducer.reproducer_id},
            run_id=candidate.run_id
        )

        # 1. Manifest and Artifact Integrity Verification
        if not reproducer.verify_tamper():
            reproducer.state = ReproducerState.INVALIDATED
            self._record_event(
                EventType.REPRODUCER_INVALIDATED,
                actor="IndependentValidator",
                payload={"reproducer_id": reproducer.reproducer_id, "reason": "Manifest or artifact hash mismatch"},
                run_id=candidate.run_id
            )
            return self._build_result(
                val_id=val_id,
                request=request,
                verdict=ValidationVerdict.INCONCLUSIVE,
                confidence=0.0,
                determinism_class=DeterminismClass.UNKNOWN,
                replay_count=0,
                success_count=0,
                failure_count=0,
                reasoning="TAMPER_DETECTED: Reproducer artifact or manifest integrity failed verification. Reproducer invalidated."
            )

        # 2. Check Tool Availability (Never reject on tool unavailability!)
        missing_tools = []
        for tool in manifest.required_tools:
            if not shutil.which(tool):
                missing_tools.append(tool)

        if missing_tools:
            self._record_event(
                EventType.VALIDATION_INCONCLUSIVE,
                actor="IndependentValidator",
                payload={"missing_tools": missing_tools},
                run_id=candidate.run_id
            )
            return self._build_result(
                val_id=val_id,
                request=request,
                verdict=ValidationVerdict.INCONCLUSIVE,
                confidence=0.0,
                determinism_class=DeterminismClass.UNKNOWN,
                replay_count=0,
                success_count=0,
                failure_count=0,
                reasoning=f"TOOL_UNAVAILABLE: Required verification tool(s) not found in environment: {', '.join(missing_tools)}."
            )

        # 3. Controlled Build Phase (if required)
        workspace = Path(request.repo_root)
        if manifest.build_command:
            build_policy = SandboxPolicy(
                mode=SandboxMode.CONTROLLED_BUILD,
                timeout_seconds=30.0,
                allow_network=False
            )
            build_res = self.sandbox_runner.execute(
                command=manifest.build_command,
                workspace=workspace,
                policy=build_policy
            )
            if build_res.trace.exit_code != 0:
                self._record_event(
                    EventType.VALIDATION_INCONCLUSIVE,
                    actor="IndependentValidator",
                    payload={"build_command": manifest.build_command, "exit_code": build_res.trace.exit_code},
                    run_id=candidate.run_id
                )
                return self._build_result(
                    val_id=val_id,
                    request=request,
                    verdict=ValidationVerdict.INCONCLUSIVE,
                    confidence=0.0,
                    determinism_class=DeterminismClass.UNKNOWN,
                    replay_count=0,
                    success_count=0,
                    failure_count=0,
                    traces=[build_res.trace],
                    reasoning=f"BUILD_FAILED: Controlled build failed with exit code {build_res.trace.exit_code}. Tool/build failure is not rejected."
                )

        # 4. Primary Validation Execution in Sandbox
        exec_policy = SandboxPolicy(
            mode=SandboxMode.UNTRUSTED_REPRODUCTION,
            timeout_seconds=20.0,
            allow_network=False
        )

        self._record_event(
            EventType.SANDBOX_STARTED,
            actor="IndependentValidator",
            payload={"run_type": "primary", "reproducer_id": reproducer.reproducer_id},
            run_id=candidate.run_id
        )

        primary_res = self.sandbox_runner.execute(
            command=manifest.run_command,
            workspace=workspace,
            policy=exec_policy
        )

        # If sandbox infrastructure itself failed (e.g., timeout, crash, policy block)
        if primary_res.status.value in ["SANDBOX_FAILED", "POLICY_BLOCKED", "RESOURCE_EXHAUSTED", "ENVIRONMENT_FAILED"]:
            self._record_event(
                EventType.SANDBOX_FAILED,
                actor="IndependentValidator",
                payload={"status": primary_res.status.value, "stderr": primary_res.stderr},
                run_id=candidate.run_id
            )
            return self._build_result(
                val_id=val_id,
                request=request,
                verdict=ValidationVerdict.INCONCLUSIVE,
                confidence=0.0,
                determinism_class=DeterminismClass.UNKNOWN,
                replay_count=1,
                success_count=0,
                failure_count=0,
                traces=[primary_res.trace],
                reasoning=f"SANDBOX_EXECUTION_FAILED: Sandbox reported {primary_res.status.value}. Unable to safely observe execution."
            )

        self._record_event(
            EventType.SANDBOX_COMPLETED,
            actor="IndependentValidator",
            payload={"exit_code": primary_res.exit_code},
            run_id=candidate.run_id
        )

        # Evaluate primary run against expected failure
        primary_reproduced, primary_signal = self._evaluate_failure_signal(
            manifest=manifest,
            exit_code=primary_res.exit_code,
            stdout=primary_res.stdout,
            stderr=primary_res.stderr
        )

        all_traces = [primary_res.trace]
        replay_traces = []

        # 5. Multi-Pass Determinism Probing
        requested_replays = max(1, request.requested_replay_count)
        reproduced_counts = 1 if primary_reproduced else 0
        failure_counts = 0 if primary_reproduced else 1
        fingerprints = [self._compute_trace_fingerprint(primary_res.trace, primary_signal)]

        self._record_event(
            EventType.REPLAY_STARTED,
            actor="IndependentValidator",
            payload={"requested_replays": requested_replays},
            run_id=candidate.run_id
        )

        raw_matches = True
        semantic_matches = True

        for i in range(1, requested_replays):
            replay_res = self.sandbox_runner.execute(
                command=manifest.run_command,
                workspace=workspace,
                policy=exec_policy
            )
            all_traces.append(replay_res.trace)
            replay_traces.append(replay_res.trace.sandbox_execution_id)

            reproduced, sig = self._evaluate_failure_signal(
                manifest=manifest,
                exit_code=replay_res.exit_code,
                stdout=replay_res.stdout,
                stderr=replay_res.stderr
            )
            if reproduced:
                reproduced_counts += 1
            else:
                failure_counts += 1

            fp = self._compute_trace_fingerprint(replay_res.trace, sig)
            fingerprints.append(fp)

            if replay_res.exit_code != primary_res.exit_code:
                raw_matches = False
            if sig != primary_signal:
                semantic_matches = False

        self._record_event(
            EventType.REPLAY_COMPLETED,
            actor="IndependentValidator",
            payload={"reproduced_count": reproduced_counts, "total_runs": requested_replays},
            run_id=candidate.run_id
        )

        # Classify determinism
        if reproduced_counts == requested_replays:
            det_class = DeterminismClass.DETERMINISTIC
        elif failure_counts == requested_replays and primary_res.exit_code == 0 and all(t.exit_code == 0 for t in all_traces):
            det_class = DeterminismClass.DETERMINISTIC
        elif reproduced_counts == 0:
            det_class = DeterminismClass.NON_REPRODUCING
        elif reproduced_counts > 0 and failure_counts > 0:
            det_class = DeterminismClass.FLAKY
        else:
            det_class = DeterminismClass.VARIABLE

        # 6. Minimization Verification (if minimization was requested/performed)
        minimization_res = None
        if manifest.minimization_metadata:
            minimization_res = self._verify_minimization(
                request=request,
                workspace=workspace,
                policy=exec_policy
            )
            if minimization_res and minimization_res.reproduction_verified_by_validator:
                self._record_event(
                    EventType.MINIMIZATION_COMPLETED,
                    actor="IndependentValidator",
                    payload={"verified": True, "retained_hash": minimization_res.retained_artifact_hash},
                    run_id=candidate.run_id
                )

        # 7. Authoritative Verdict Determination
        # Section 34 (CONFIRMED): Deterministic positive evidence reproducing the defect
        # Section 35 (REJECTED): Deterministic positive evidence proving security control upheld (hard negative)
        # Section 36 (INCONCLUSIVE): Variable/flaky, non-reproducing without hard negative proof, tool/env error
        evidence_ids = []
        if det_class == DeterminismClass.DETERMINISTIC and primary_reproduced:
            verdict = ValidationVerdict.CONFIRMED
            confidence = 1.0
            reasoning = (
                f"CONFIRMED: Vulnerability deterministically reproduced across {requested_replays} sandboxed runs. "
                f"Observed signal: '{primary_signal}' matching expected failure."
            )
            reproducer.state = ReproducerState.CONFIRMED
            self._record_event(EventType.VALIDATION_CONFIRMED, actor="IndependentValidator", payload={"reasoning": reasoning}, run_id=candidate.run_id)

        elif det_class == DeterminismClass.DETERMINISTIC and not primary_reproduced:
            # Check if this is a validated Hard Negative (target executed cleanly, assertion passed, control prevented defect)
            if primary_res.exit_code == 0:
                verdict = ValidationVerdict.REJECTED
                confidence = 0.95
                reasoning = (
                    f"REJECTED: Target deterministically executed cleanly without defect (exit code 0). "
                    f"Positive contradictory evidence establishes the security control / invariant held."
                )
                reproducer.state = ReproducerState.REJECTED
                self._record_event(EventType.VALIDATION_REJECTED, actor="IndependentValidator", payload={"reasoning": reasoning}, run_id=candidate.run_id)
            else:
                verdict = ValidationVerdict.INCONCLUSIVE
                confidence = 0.3
                reasoning = (
                    f"INCONCLUSIVE: Execution exited with code {primary_res.exit_code} but did not produce "
                    f"expected failure signal '{manifest.expected_failure}'."
                )
                reproducer.state = ReproducerState.INCONCLUSIVE
                self._record_event(EventType.VALIDATION_INCONCLUSIVE, actor="IndependentValidator", payload={"reasoning": reasoning}, run_id=candidate.run_id)

        elif det_class in [DeterminismClass.FLAKY, DeterminismClass.VARIABLE]:
            verdict = ValidationVerdict.INCONCLUSIVE
            confidence = 0.4
            reasoning = (
                f"INCONCLUSIVE: Reproducer exhibited unstable/flaky behavior ({reproduced_counts}/{requested_replays} reproduced). "
                f"Architecture forbids confirming flaky replays."
            )
            reproducer.state = ReproducerState.INCONCLUSIVE
            self._record_event(EventType.VALIDATION_INCONCLUSIVE, actor="IndependentValidator", payload={"reasoning": reasoning}, run_id=candidate.run_id)

        else:
            verdict = ValidationVerdict.INCONCLUSIVE
            confidence = 0.1
            reasoning = f"INCONCLUSIVE: Failure did not reproduce across any of the {requested_replays} runs."
            reproducer.state = ReproducerState.INCONCLUSIVE
            self._record_event(EventType.VALIDATION_INCONCLUSIVE, actor="IndependentValidator", payload={"reasoning": reasoning}, run_id=candidate.run_id)

        # 8. Record Evidence in Evidence Plane from Sandbox Traces (LLM text remains quarantined)
        for trace in all_traces:
            ev = self._create_evidence_record(
                candidate=candidate,
                reproducer=reproducer,
                trace=trace,
                val_id=val_id
            )
            evidence_ids.append(ev.evidence_id)

        self._record_event(
            EventType.VALIDATION_COMPLETED,
            actor="IndependentValidator",
            payload={"verdict": verdict.value, "confidence": confidence},
            run_id=candidate.run_id
        )

        return ValidationResult(
            validation_id=val_id,
            candidate_id=candidate.candidate_id,
            reproducer_id=reproducer.reproducer_id,
            verdict=verdict,
            confidence_score=confidence,
            determinism=DeterminismResult(
                determinism_class=det_class,
                replay_count=requested_replays,
                success_count=reproduced_counts,
                failure_count=failure_counts,
                failure_rate=failure_counts / float(requested_replays),
                fingerprint_set=fingerprints,
                details={"raw_match": raw_matches, "semantic_match": semantic_matches}
            ),
            replay_comparison=ReplayComparison(
                primary_run_id=primary_res.trace.sandbox_execution_id,
                replay_run_ids=replay_traces,
                raw_match=raw_matches,
                canonical_match=raw_matches,
                semantic_match=semantic_matches,
                observed_failure_signal=primary_signal,
                match_policy="semantic",
                tolerances={"exit_code_strict": True}
            ),
            minimization=minimization_res,
            supporting_evidence_ids=evidence_ids,
            execution_trace_ids=[t.sandbox_execution_id for t in all_traces],
            reasoning=reasoning
        )

    def _evaluate_failure_signal(self, manifest, exit_code: int, stdout: str, stderr: str) -> tuple[bool, str]:
        """
        Compares observed execution output against declared expected failure signal.
        """
        combined_output = f"{stdout}\n{stderr}"
        expected_failure = manifest.expected_failure or {}
        exp_code = expected_failure.get("exit_code")
        exp_pattern = expected_failure.get("pattern") or expected_failure.get("signal")
        exp_assertion = expected_failure.get("assertion")

        # 1. If explicit non-zero exit code expected
        if exp_code is not None and exit_code == exp_code:
            signal = f"Exit code {exit_code} matched expected"
            if exp_pattern:
                if re.search(str(exp_pattern), combined_output):
                    return True, f"{signal} and pattern '{exp_pattern}' matched"
                return False, f"Exit code matched but pattern '{exp_pattern}' missing"
            return True, signal

        # 2. Check assertion / crash pattern in output
        if exp_assertion and exp_assertion in combined_output:
            return True, f"Assertion violation '{exp_assertion}' observed"

        if exp_pattern and re.search(str(exp_pattern), combined_output):
            return True, f"Pattern '{exp_pattern}' observed in execution trace"

        # 3. Known failure keywords if expected failure says crash/violation
        if exit_code != 0:
            for kw in ["AssertionError", "SIGSEGV", "core dumped", "panicked at", "Fatal error", "Security violation"]:
                if kw in combined_output:
                    return True, f"Crash/Violation observed: {kw}"

        return False, f"Process exited with {exit_code} (no expected failure signal matched)"

    def _compute_trace_fingerprint(self, trace: ExecutionTrace, signal: str) -> str:
        """Computes a semantic SHA256 fingerprint for a sandbox execution trace."""
        content = f"{trace.exit_code}:{trace.stdout_hash}:{trace.stderr_hash}:{signal}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _verify_minimization(self, request: ValidationRequest, workspace: Path, policy: SandboxPolicy) -> MinimizationResult:
        """
        Independently re-verifies minimization by executing the minimized candidate in the sandbox.
        Guarantees that if minimized fails to reproduce, baseline artifact is retained.
        """
        manifest = request.reproducer.manifest
        meta = manifest.minimization_metadata
        orig_hash = meta.get("original_hash", "")
        min_hash = meta.get("minimized_hash", "")
        min_run_cmd = meta.get("minimized_run_command", manifest.run_command)

        min_res = self.sandbox_runner.execute(
            command=min_run_cmd,
            workspace=workspace,
            policy=policy
        )

        min_reproduced, _ = self._evaluate_failure_signal(
            manifest=manifest,
            exit_code=min_res.exit_code,
            stdout=min_res.stdout,
            stderr=min_res.stderr
        )

        if min_reproduced:
            return MinimizationResult(
                original_hash=orig_hash,
                minimized_hash=min_hash,
                original_size=meta.get("original_size", 0),
                minimized_size=meta.get("minimized_size", 0),
                reduction_percentage=meta.get("reduction_percentage", 0.0),
                reproduction_verified_by_validator=True,
                retained_artifact_hash=min_hash
            )
        else:
            # Baseline retention guarantee
            return MinimizationResult(
                original_hash=orig_hash,
                minimized_hash=min_hash,
                original_size=meta.get("original_size", 0),
                minimized_size=meta.get("minimized_size", 0),
                reduction_percentage=meta.get("reduction_percentage", 0.0),
                reproduction_verified_by_validator=False,
                retained_artifact_hash=orig_hash
            )

    def _create_evidence_record(self, candidate: Candidate, reproducer: Reproducer, trace: ExecutionTrace, val_id: str) -> Evidence:
        """
        Generates and saves structured Evidence to the Evidence Plane.
        Enforces that validator evidence is strictly derived from observed sandbox execution traces.
        """
        ev_id = f"evd-{uuid.uuid4().hex[:12]}"
        cmd_str = " ".join(trace.command) if isinstance(trace.command, list) else str(trace.command)
        canonical_content = f"{cmd_str}\n{trace.exit_code}\n{trace.stdout_hash}"
        canonical_hash = hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()
        semantic_fp = hashlib.sha256(f"{trace.exit_code}:{trace.wall_time_seconds}".encode("utf-8")).hexdigest()

        evidence = Evidence(
            evidence_id=ev_id,
            task_id=candidate.task_id,
            run_id=candidate.run_id,
            agent_id="IndependentValidator",
            source_type=EvidenceSourceType.VALIDATOR_RESULT,
            tool="SandboxRunner",
            command=cmd_str,
            raw_hash=trace.stdout_hash,
            canonical_hash=canonical_hash,
            semantic_fingerprint=semantic_fp,
            environment_fingerprint=trace.environment_fingerprint,
            exit_status=trace.exit_code,
            provenance_links=[
                f"sandbox_exec:{trace.sandbox_execution_id}",
                f"reproducer:{reproducer.reproducer_id}",
                f"val_run:{val_id}"
            ]
        )

        if self.db:
            try:
                with self.db.get_connection() as conn:
                    conn.execute("""
                        INSERT INTO evidence (
                            evidence_id, task_id, run_id, agent_id, source_type,
                            raw_hash, canonical_hash, semantic_fingerprint,
                            environment_fingerprint, exit_status, provenance, schema_version
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        evidence.evidence_id,
                        evidence.task_id,
                        evidence.run_id,
                        evidence.agent_id,
                        evidence.source_type.value,
                        evidence.raw_hash,
                        evidence.canonical_hash,
                        evidence.semantic_fingerprint,
                        evidence.environment_fingerprint,
                        evidence.exit_status,
                        json.dumps(evidence.provenance_links),
                        evidence.schema_version
                    ))
                    conn.commit()
            except Exception:
                pass

        return evidence

    def _build_result(self, val_id: str, request: ValidationRequest, verdict: ValidationVerdict,
                      confidence: float, determinism_class: DeterminismClass, replay_count: int,
                      success_count: int, failure_count: int, reasoning: str,
                      traces: Optional[List[ExecutionTrace]] = None) -> ValidationResult:
        """Helper to construct structured ValidationResult for early exits."""
        valid_traces = [t for t in (traces or []) if t is not None]
        evidence_ids = []
        for t in valid_traces:
            ev = self._create_evidence_record(request.candidate, request.reproducer, t, val_id)
            evidence_ids.append(ev.evidence_id)

        return ValidationResult(
            validation_id=val_id,
            candidate_id=request.candidate.candidate_id,
            reproducer_id=request.reproducer.reproducer_id,
            verdict=verdict,
            confidence_score=confidence,
            determinism=DeterminismResult(
                determinism_class=determinism_class,
                replay_count=replay_count,
                success_count=success_count,
                failure_count=failure_count,
                failure_rate=0.0 if replay_count == 0 else failure_count / float(replay_count)
            ),
            replay_comparison=ReplayComparison(
                primary_run_id=valid_traces[0].sandbox_execution_id if valid_traces else "none",
                raw_match=False,
                canonical_match=False,
                semantic_match=False,
                observed_failure_signal="",
                match_policy="semantic"
            ),
            supporting_evidence_ids=evidence_ids,
            execution_trace_ids=[t.sandbox_execution_id for t in valid_traces],
            reasoning=reasoning
        )
