"""
Test verification script for Scoped Subdirectory Analysis and Language-Aware Tool Routing
against the real Caliptra runtime benchmark component:
/home/hackdac/Documents/Benchmark/caliptra-vuln-known/runtime
"""

import sys
import json
import pytest
import asyncio
from pathlib import Path

from api.routers.projects import _inspect_directory_deterministic
from orchestrator.tool_router import route_tools_for_scope
from repository_intelligence.rust_security_scanner import scan_rust_security_surfaces
from supervisor.supervisor import Supervisor
from orchestrator.orchestrator import CentralOrchestrator
from history.database import DatabaseService
from history.project_repository import ProjectRepository
from history.soc_repositories import VerificationPlanRepository, WorkPackageRepository


CALIPTRA_RUNTIME_DIR = "/home/hackdac/Documents/Benchmark/caliptra-vuln-known/runtime"


def test_runtime_subdirectory_intake():
    assert Path(CALIPTRA_RUNTIME_DIR).exists(), f"Benchmark directory not found: {CALIPTRA_RUNTIME_DIR}"
    
    intake = _inspect_directory_deterministic(CALIPTRA_RUNTIME_DIR)
    
    # 1. Verification of classification and language
    assert intake["primary_language"] == "Rust", f"Expected Rust, got {intake['primary_language']}"
    assert "Rust" in intake["classification"], f"Expected Rust classification, got {intake['classification']}"
    assert intake["rust_count"] > 100, f"Expected >100 Rust files, got {intake['rust_count']}"
    assert intake["rtl_count"] == 0, f"Expected 0 RTL files, got {intake['rtl_count']}"
    assert intake["build_system"] == "Cargo", f"Expected Cargo, got {intake['build_system']}"
    
    # 2. Scope rule: Subdirectory component detection
    assert intake["scope_type"] == "SUBDIRECTORY_COMPONENT", f"Expected SUBDIRECTORY_COMPONENT, got {intake['scope_type']}"
    assert intake["parent_repository_if_known"] is not None
    assert "caliptra-vuln-known" in intake["parent_repository_if_known"]
    assert len(intake["parent_components"]) > 0
    print("\n[+] Intake check passed: Subdirectory Rust firmware correctly detected with parent repo.")


def test_language_aware_tool_routing():
    intake = _inspect_directory_deterministic(CALIPTRA_RUNTIME_DIR)
    explanation = route_tools_for_scope(CALIPTRA_RUNTIME_DIR, intake)
    
    # 1. Primary tool must NOT be Yosys or Verilator
    assert explanation.primary_tool in ("rust_source_inspector", "ripgrep (rg)", "deterministic_reproducer")
    assert "yosys" not in explanation.recommended_tools
    assert "verilator" not in explanation.recommended_tools
    
    # 2. Rejection must be explicit and explainable
    rejected_names = [r["tool"] for r in explanation.rejected_tools]
    assert "yosys" in rejected_names, "Expected yosys in rejected_tools"
    assert "verilator" in rejected_names, "Expected verilator in rejected_tools"
    
    yosys_rejection = next(r for r in explanation.rejected_tools if r["tool"] == "yosys")
    assert "No RTL" in yosys_rejection["reason"]
    print("[+] Tool routing check passed: Yosys rejected with explicit explainability reason.")


def test_security_surface_and_vulnerability_extraction():
    surfaces, vulns = scan_rust_security_surfaces(CALIPTRA_RUNTIME_DIR)
    
    assert len(surfaces) >= 10, f"Expected at least 10 security surfaces, got {len(surfaces)}"
    assert len(vulns) >= 10, f"Expected at least 10 candidate vulnerabilities, got {len(vulns)}"
    
    titles = [v.title for v in vulns]
    assert any("PAUSER" in t for t in titles), "PAUSER privilege truncation (V001) not found"
    assert any("PCR" in t for t in titles), "PCR log extension (V003) not found"
    assert any("Key Ladder" in t for t in titles), "Key Ladder underflow (V004) not found"
    assert any("DPE" in t for t in titles), "DPE privilege inversion (V008) not found"
    
    # Context requirement verification
    pauser_vuln = next(v for v in vulns if "PAUSER" in v.title)
    assert pauser_vuln.requires_parent_context is True
    assert pauser_vuln.context_explanation is not None
    print("[+] Security surface & vulnerability extraction passed: V001, V003, V004, V008 detected with context flags.")


@pytest.mark.asyncio
async def test_end_to_end_runtime_execution(tmp_path):
    # Use isolated test database
    db_file = tmp_path / "test_llmorch.db"
    db = DatabaseService(str(db_file))
    
    proj_repo = ProjectRepository(db)
    proj = proj_repo.create_project(
        name="Caliptra Runtime Benchmark",
        target_directory=CALIPTRA_RUNTIME_DIR,
        metadata={"description": "End to end test of scoped runtime analysis"}
    )
    project_id = proj["project_id"]
    proj_repo.set_active_project(project_id)
    
    # 1. Plan generation
    supervisor = Supervisor(db)
    plan, work_packages, objectives, questions = supervisor.generate_plan(
        repository_path=CALIPTRA_RUNTIME_DIR,
        repository_name="caliptra-runtime",
        intent_objective="Find security vulnerabilities in Caliptra runtime firmware"
    )
    
    assert plan is not None
    assert len(work_packages) > 0
    assert len(objectives) > 0
    # Proposed questions should include parent repository context decision
    assert len(questions) > 0
    assert any("runtime" in q["question"].lower() for q in questions)

    # Save plan and work packages
    plan_repo = VerificationPlanRepository(db)
    wp_repo = WorkPackageRepository(db)
    plan.project_id = project_id
    plan_repo.save(plan)
    for wp in work_packages:
        wp_repo.save(wp)
    
    # 2. Plan Approval & Execution
    orchestrator = CentralOrchestrator(db)
    exec_res = await orchestrator.approve_and_execute_plan(
        plan_id=plan.plan_id,
        project_id=project_id
    )
    
    run_id = exec_res["run"]["run_id"]
    task_ids = exec_res["task_ids"]
    assert len(task_ids) > 0
    
    # Run the execution loop
    await orchestrator.dispatch_and_execute_run(
        run_id=run_id,
        plan_id=plan.plan_id,
        project_id=project_id,
        task_ids=task_ids
    )
    
    # 3. Verify Database Records
    with db.get_connection() as conn:
        # Check findings
        findings = conn.execute("SELECT * FROM findings WHERE project_id = ?", (project_id,)).fetchall()
        assert len(findings) >= 10, f"Expected at least 10 findings, found {len(findings)}"
        
        # Check evidence linkage
        evidence = conn.execute("SELECT * FROM evidence WHERE project_id = ?", (project_id,)).fetchall()
        assert len(evidence) >= 10, f"Expected at least 10 evidence items, found {len(evidence)}"
        
        for e in evidence:
            assert e["source_tool"] is not None and e["source_tool"] != "", f"Empty source_tool in evidence {e['evidence_id']}"
            assert e["timestamp"] is not None and e["timestamp"] != "", f"Empty timestamp in evidence {e['evidence_id']}"
            assert e["exit_code"] == 0
        
        # Check tool executions: ensure Yosys was NEVER executed
        tool_execs = conn.execute("SELECT * FROM tool_executions WHERE project_id = ?", (project_id,)).fetchall()
        assert len(tool_execs) > 0
        executed_tool_names = [te["tool_name"] for te in tool_execs]
        assert "yosys" not in executed_tool_names, "CRITICAL ERROR: Yosys was executed on pure Rust crate!"
        assert "verilator" not in executed_tool_names, "CRITICAL ERROR: Verilator was executed on pure Rust crate!"
        assert "rust_source_inspector" in executed_tool_names
        assert "deterministic_reproducer" in executed_tool_names
        
    print(f"\n[+] E2E Execution Succeeded: {len(findings)} findings validated, {len(evidence)} evidence linked, 0 Yosys calls.")
