"""
Script to execute the complete real LLMorch security analysis pipeline
against the actual Caliptra runtime benchmark component:
/home/hackdac/Documents/Benchmark/caliptra-vuln-known/runtime
"""

import sys
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime, timezone

# Add LLMorch root
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from history.database import DatabaseService, get_db_path
from history.project_repository import ProjectRepository
from history.soc_repositories import VerificationPlanRepository, WorkPackageRepository
from api.routers.projects import _inspect_directory_deterministic
from orchestrator.tool_router import route_tools_for_scope
from supervisor.supervisor import Supervisor
from orchestrator.orchestrator import CentralOrchestrator
from evaluation.benchmark_oracle_comparator import evaluate_findings_against_benchmark


CALIPTRA_RUNTIME_DIR = "/home/hackdac/Documents/Benchmark/caliptra-vuln-known/runtime"


async def main():
    print("======================================================================")
    print("LLMORCH REAL BENCHMARK EXECUTION: CALIPTRA RUNTIME")
    print(f"Target: {CALIPTRA_RUNTIME_DIR}")
    print("======================================================================\n")

    db = DatabaseService(get_db_path())
    proj_repo = ProjectRepository(db)

    # 1. Project Creation & Intake
    t0 = time.time()
    intake = _inspect_directory_deterministic(CALIPTRA_RUNTIME_DIR)
    print(f"[1] Deterministic Intake Complete:")
    print(f"    - Classification: {intake['classification']}")
    print(f"    - Scope Type: {intake['scope_type']}")
    print(f"    - Primary Language: {intake['primary_language']}")
    print(f"    - Build System: {intake['build_system']}")
    print(f"    - Files Analyzable: {intake['total_files']} (Rust: {intake['rust_count']}, RTL: {intake['rtl_count']})")
    print(f"    - Parent Repository: {intake['parent_repository_if_known']}")
    print(f"    - Discovered Parent Components: {', '.join(intake['parent_components'][:5])}...\n")

    proj = proj_repo.create_project(
        name="Caliptra Runtime Benchmark",
        target_directory=CALIPTRA_RUNTIME_DIR,
        metadata={"intake": intake, "description": "Intentionally vulnerable benchmark component"}
    )
    project_id = proj["project_id"]
    proj_repo.set_active_project(project_id)

    # 2. Tool Routing & Explainability
    routing = route_tools_for_scope(CALIPTRA_RUNTIME_DIR, intake)
    print(f"[2] Language-Aware Tool Routing:")
    print(f"    - Target: {routing.target}")
    print(f"    - Detected Language: {routing.detected_language}")
    print(f"    - Analysis Method: {routing.analysis_method}")
    print(f"    - Recommended Tools: {', '.join(routing.recommended_tools)}")
    print(f"    - Rationale: {routing.selection_rationale}")
    print(f"    - Explicitly Rejected Tools:")
    for r in routing.rejected_tools:
        print(f"      * {r['tool']}: {r['reason']}")
    print()

    # 3. Supervisor Verification Planning
    supervisor = Supervisor(db)
    plan, work_packages, objectives, questions = supervisor.synthesize_verification_plan(
        repository_path=CALIPTRA_RUNTIME_DIR,
        repository_name="caliptra-runtime",
        intent_objective="Find security vulnerabilities in Caliptra runtime firmware"
    )
    plan.project_id = project_id
    plan_repo = VerificationPlanRepository(db)
    wp_repo = WorkPackageRepository(db)
    plan_repo.save(plan)
    for wp in work_packages:
        wp.project_id = project_id
        wp_repo.save(wp)

    print(f"[3] Supervisor Verification Plan Synthesized:")
    print(f"    - Plan ID: {plan.plan_id}")
    print(f"    - Work Packages: {len(work_packages)}")
    print(f"    - Objectives: {len(objectives)}")
    print(f"    - Proposed Questions: {len(questions)}")
    for q in questions:
        print(f"      * Scope Decision: {q['question']}")
    print()

    # 4. Orchestration & Execution
    orchestrator = CentralOrchestrator(db)
    exec_res = await orchestrator.approve_and_execute_plan(
        plan_id=plan.plan_id,
        project_id=project_id
    )

    run_id = exec_res["run"]["run_id"]
    task_ids = exec_res["task_ids"]
    print(f"[4] Orchestrator Executing Plan:")
    print(f"    - Run ID: {run_id}")
    print(f"    - Tasks Dispatched: {len(task_ids)}")

    await orchestrator.dispatch_and_execute_run(
        run_id=run_id,
        plan_id=plan.plan_id,
        project_id=project_id,
        task_ids=task_ids
    )

    duration = time.time() - t0
    print(f"    - Execution Completed in {duration:.2f}s\n")

    # 5. Database Verification & Tool Execution Auditing
    with db.get_connection() as conn:
        findings_rows = conn.execute("SELECT * FROM findings WHERE project_id = ?", (project_id,)).fetchall()
        findings = [dict(r) for r in findings_rows]
        
        evidence_rows = conn.execute("SELECT * FROM evidence WHERE project_id = ?", (project_id,)).fetchall()
        evidence = [dict(r) for r in evidence_rows]
        
        tool_rows = conn.execute("SELECT * FROM tool_executions WHERE project_id = ?", (project_id,)).fetchall()
        tools = [dict(r) for r in tool_rows]

    print(f"[5] Audit Records Linkage:")
    print(f"    - Findings Inserted: {len(findings)}")
    print(f"    - Evidence Records Linked: {len(evidence)}")
    print(f"    - Tool Executions Recorded: {len(tools)}")
    
    tools_used = sorted(list({t['tool_name'] for t in tools}))
    print(f"    - Real Tools Executed: {', '.join(tools_used)}")
    assert "yosys" not in tools_used, "CRITICAL ERROR: Yosys executed on pure Rust crate!"
    assert "verilator" not in tools_used, "CRITICAL ERROR: Verilator executed on pure Rust crate!"
    print(f"    - Verified: Yosys and Verilator were NOT executed.")

    # 6. Benchmark Evaluation against Ground Truth Oracle
    print(f"\n[6] Benchmark Oracle Evaluation (Hiding oracle during analysis):")
    report = evaluate_findings_against_benchmark(findings, target_scope="runtime")
    print(f"    - Total Oracle Vulnerabilities: {report.total_oracle_vulnerabilities}")
    print(f"    - In-Scope Vulnerabilities for runtime/: {report.in_scope_vulnerabilities_count}")
    print(f"    - Discovered Candidates Matching Oracle: {report.matched_in_scope_count}/{report.in_scope_vulnerabilities_count} ({report.matched_in_scope_percentage}%)")
    print(f"    - Context Escalation Recognition Accuracy: {report.context_escalation_accuracy}%\n")

    print("Detailed Benchmark Matches:")
    for m in report.matches:
        if m.is_in_scope:
            status = f"✓ CONFIRMED ({m.matched_finding_id})" if m.matched else "✗ MISSED"
            ctx_flag = " [REQUIRES PARENT CONTEXT]" if m.is_cross_component else " [LOCAL]"
            print(f"  [{m.benchmark_id}] {m.benchmark_title}{ctx_flag}")
            print(f"       File: {m.benchmark_file} -> {status}")
            if m.matched:
                print(f"       Finding: {m.matched_finding_title[:90]}...")
            print()

    print(f"Real execution successful! Duration: {duration:.2f}s.")


if __name__ == "__main__":
    asyncio.run(main())
