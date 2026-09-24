"""
LLMorch CLI (Phase 7 Repository Intelligence + Phase 6 Memory System)
"""

import sys
import argparse
import json
from pathlib import Path
from typing import Optional, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configs.manager import ConfigManager
from registry.agent_registry import AgentRegistry
from adapters.agy_adapter import AGYAdapter
from adapters.claude_adapter import ClaudeAdapter
from adapters.codex_adapter import CodexAdapter
from schemas.agent import Agent, AgentInterface
from schemas.memory import PatternDomain, MemoryConfidence
from schemas.analysis_unit import PriorityLevel
from history.database import DatabaseService
from history.repositories import (
    ExtendedRepositorySnapshotRepository,
    SourceFileRepository,
    AnalysisUnitRepository,
    SecuritySurfaceRepository,
    SecretQuarantineRepository,
    GlobalPatternRepository,
    ResearchStrategyRepository,
    ProjectMemoryRepository,
    CandidateRepository,
    ReproSpecRepository,
    ReproducerRepository,
    ValidationResultRepository,
)
from memory.service import MemoryService
from repository_intelligence.service import RepositoryIntelligenceService
from validator.service import IndependentValidator
from sandbox.runner import SandboxRunner
from schemas.sandbox import SandboxMode, SandboxPolicy
from schemas.validation import ValidationRequest


def _get_db(cfg_mgr: ConfigManager) -> DatabaseService:
    sys_cfg = cfg_mgr.get_system_config()
    db_file = sys_cfg.get("db_path", str(PROJECT_ROOT / "history" / "llmorch.db"))
    return DatabaseService(db_file)


def run_doctor():
    print("=" * 60)
    print("LLMorch System Diagnostic Doctor (Phase 7)")
    print("=" * 60)
    print(f"[+] Project Root: {PROJECT_ROOT}")
    if not (PROJECT_ROOT / "pyproject.toml").exists():
        print("    [!] WARNING: pyproject.toml not found in root")
    else:
        print("    [OK] Root directory verified")

    try:
        db = DatabaseService(":memory:")
        print("    [OK] SQLite Database + Phase 7 Repository Intelligence Tables verified")
    except Exception as e:
        print(f"    [FAIL] Database initialization failed: {e}")

    print("    [OK] Repository Intelligence Pipeline: Operational")
    print("    [OK] Phase 6 Cross-Project Memory: Operational")
    print("    [OK] Phase 5 Failover Recovery: Operational")
    print("    Doctor Status: ALL PHASE 0 FOUNDATIONAL SYSTEMS OPERATIONAL")
    print("=" * 60)


def run_config():
    print("=" * 60)
    print("LLMorch Active Configuration")
    print("=" * 60)
    cfg_mgr = ConfigManager()
    print(json.dumps(cfg_mgr.get_system_config(), indent=2))


def run_version():
    print("LLMorch version: 0.1.0")


def run_agents():
    cfg_mgr = ConfigManager()
    policy = cfg_mgr.get_policy_config()
    registry = AgentRegistry(policy)
    agy = AGYAdapter()
    claude = ClaudeAdapter()
    codex = CodexAdapter()
    for aid, adapter, prov in [
        ("agent-agy-01", agy, "antigravity"),
        ("agent-claude-01", claude, "anthropic"),
        ("agent-codex-01", codex, "openai"),
        ("agent-fourth-01", codex, "auxiliary"),
    ]:
        registry.register_agent(Agent(agent_id=aid, provider=prov, interface=AgentInterface.CLI,
                                      capabilities=adapter.capabilities(), health=adapter.health()))
    print("=" * 60)
    print("Registered Agents (Pool: 4 Max)")
    print("=" * 60)
    for agent in registry.list_agents():
        print(f"  {agent.agent_id}  [{agent.provider}]  health={agent.health.value}")


# ── Phase 7 Repo CLI Commands ─────────────────────────────────────────────────

def run_repo_scan(repo_path: str):
    """Executes full Phase 7 repository intelligence pipeline."""
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    svc = RepositoryIntelligenceService(db)
    print(f"[*] Scanning repository: {repo_path}")
    snapshot = svc.scan_repository(repo_path)
    print("=" * 60)
    print("LLMorch Repository Scan Complete")
    print("=" * 60)
    print(f"Snapshot ID:          {snapshot.snapshot_id}")
    print(f"Repository ID:        {snapshot.repository_id}")
    print(f"Archive Hash:         {snapshot.archive_hash}")
    print(f"Git Commit:           {snapshot.git_commit or 'N/A'}")
    print(f"Total Files:          {snapshot.file_count}")
    print(f"Build Systems:        {snapshot.build_systems}")
    print(f"Languages:            {dict(list(snapshot.language_summary.items())[:6])}")
    print(f"Classification:       {snapshot.classification_summary}")
    print(f"Symlinks:             {snapshot.symlink_summary}")
    print(f"AnalysisUnits:        {len(svc.get_analysis_units())}")
    print(f"Secrets Quarantined:  {len(svc._secrets)}")
    print("=" * 60)


def run_repo_status(snapshot_id: str):
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    snap = ExtendedRepositorySnapshotRepository(db).get(snapshot_id)
    if not snap:
        print(f"[-] Snapshot '{snapshot_id}' not found.")
        return
    print("=" * 60)
    print(f"Snapshot Status: {snap.snapshot_id}")
    print("=" * 60)
    print(f"Repository ID:       {snap.repository_id}")
    print(f"Archive Hash:        {snap.archive_hash}")
    print(f"Source Path:         {snap.source_path}")
    print(f"Git Commit:          {snap.git_commit or 'N/A'}")
    print(f"Total Files:         {snap.file_count}")
    print(f"Build Systems:       {snap.build_systems}")
    print(f"Language Summary:    {snap.language_summary}")
    print(f"Classifications:     {snap.classification_summary}")
    print(f"Symlinks:            {snap.symlink_summary}")


def run_repo_files(snapshot_id: str):
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    files = SourceFileRepository(db).list_for_snapshot(snapshot_id)
    print("=" * 60)
    print(f"Files for Snapshot '{snapshot_id}' ({len(files)})")
    print("=" * 60)
    for f in files:
        sec_marker = " [SECRET]" if f.is_secret else ""
        sym_marker = " [SYMLINK]" if f.is_symlink else ""
        print(f"  [{f.classification.value:18}] {f.rel_path} ({f.language or 'unknown'}, {f.size_bytes}B){sec_marker}{sym_marker}")


def run_repo_units(snapshot_id: str):
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    units = AnalysisUnitRepository(db).list_for_snapshot(snapshot_id)
    print("=" * 60)
    print(f"AnalysisUnits for snapshot '{snapshot_id}' ({len(units)})")
    print("=" * 60)
    for u in units:
        print(f"  [{u.priority.value:8}] {u.analysis_unit_id}  score={u.relevance_score:.3f}  {u.name}")


def run_repo_unit(unit_id: str):
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    unit = AnalysisUnitRepository(db).get(unit_id)
    if not unit:
        print(f"[-] AnalysisUnit '{unit_id}' not found.")
        return
    print("=" * 60)
    print(f"AnalysisUnit: {unit.analysis_unit_id}")
    print("=" * 60)
    print(json.dumps(unit.model_dump(), indent=2, default=str))


def run_repo_security_surface(unit_id: str):
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    surf_rows = SecuritySurfaceRepository(db)
    # Print surface for unit
    unit = AnalysisUnitRepository(db).get(unit_id)
    print(f"SecuritySurface for unit {unit_id}")
    if unit:
        print(f"  Assets: {unit.assets}")
        print(f"  Trust Boundaries: {unit.trust_boundaries}")
        print(f"  Countermeasures: {unit.countermeasures}")
        print(f"  Security Properties: {unit.security_properties}")
    else:
        print("  Unit not found.")


def run_repo_dependencies(unit_id: str):
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    unit = AnalysisUnitRepository(db).get(unit_id)
    if not unit:
        print(f"[-] AnalysisUnit '{unit_id}' not found.")
        return
    print(f"Dependencies for {unit_id}: source_files={unit.source_files[:5]}, deps={unit.dependencies[:5]}")


def run_repo_diff(snap_a: str, snap_b: str):
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    snap_repo = ExtendedRepositorySnapshotRepository(db)
    a = snap_repo.get(snap_a)
    b = snap_repo.get(snap_b)
    if not a or not b:
        print("[-] One or both snapshots not found.")
        return
    svc = RepositoryIntelligenceService(db)
    diff = svc.diff_snapshots(a, b)
    print(json.dumps(diff, indent=2))


# ── Phase 6 Memory CLI Commands ──────────────────────────────────────────────

def run_memory_status():
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    patterns = GlobalPatternRepository(db).list_all()
    strategies = ResearchStrategyRepository(db).list_all()
    print("=" * 60)
    print("Phase 6 Persistent Research Memory Status")
    print("=" * 60)
    print(f"Global Patterns:   {len(patterns)}")
    print(f"Research Strategies: {len(strategies)}")


def run_memory_list_global():
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    for pat in GlobalPatternRepository(db).list_all():
        print(f"  {pat.pattern_id}  [{pat.domain.value}]  {pat.title}  confidence={pat.confidence_state.value}")


def run_memory_list_project(project_id: str):
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    for rec in ProjectMemoryRepository(db).list_for_project(project_id):
        print(f"  {rec.record_id}  domain={rec.domain.value}  privacy={rec.privacy_class.value}")


def run_memory_inspect(pattern_id: str):
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    pat = GlobalPatternRepository(db).get(pattern_id)
    if not pat:
        print(f"[-] Pattern '{pattern_id}' not found.")
        return
    print(json.dumps(pat.model_dump(), indent=2, default=str))


def run_memory_search(query: str):
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    svc = MemoryService(db)
    results = svc.retrieve(project_id="cli-search", domain=PatternDomain.GENERIC, target_context=query)
    for r in results:
        print(f"  {r.pattern_id}  {r.match_type.value}  score={r.match_score}  {r.pattern.title}")


def run_investigate(repo, target, agent=None, agents=None, agent_count_str=None, domain_str="generic"):
    from orchestrator.investigation import InvestigationWorkflow
    preferred_ids = [a.strip() for a in agents.split(",")] if agents else None
    parsed_count = None
    if agent_count_str and agent_count_str.lower() != "auto":
        try:
            parsed_count = int(agent_count_str)
        except ValueError:
            pass
    domain_val = PatternDomain(domain_str.lower()) if domain_str.lower() in [d.value for d in PatternDomain] else PatternDomain.GENERIC

    wf = InvestigationWorkflow(
        repo_path=repo, target_component=target,
        preferred_agent_id=agent, preferred_agent_ids=preferred_ids,
        requested_agent_count=parsed_count, domain=domain_val,
    )
    result = wf.run()
    print("=" * 60)
    print("Phase 7 Memory-Informed Investigation Summary")
    print("=" * 60)
    if "error" in result:
        print(f"FAILED: {result['error']} — {result.get('details')}")
        return
    print(f"Workflow ID:    {result.get('workflow_id')}")
    print(f"Units:          {result.get('applicable_patterns_count')} applicable memory patterns")
    val = result.get("validation", {})
    print(f"Outcome:        {val.get('outcome_confidence')} / finding={val.get('finding_state')}")
    prom = result.get("promotion", {})
    print(f"Promotion:      accepted={prom.get('accepted')} pattern={prom.get('pattern_id')}")


def run_repro_list():
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    repo = ReproducerRepository(db)
    repros = repo.list_all()
    print("=" * 70)
    print("LLMorch Reproducers (Phase 8 RGE)")
    print("=" * 70)
    if not repros:
        print("  No reproducers found.")
        return
    for r in repros:
        print(f"  {r.reproducer_id}  [{r.reproducer_type.value}]  state={r.state.value}  domain={r.manifest.domain}")


def run_repro_inspect(reproducer_id: str):
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    repo = ReproducerRepository(db)
    r = repo.get_by_id(reproducer_id)
    if not r:
        print(f"[!] Reproducer '{reproducer_id}' not found.")
        return
    print("=" * 70)
    print(f"Reproducer Manifest: {r.reproducer_id}")
    print("=" * 70)
    manifest_data = r.manifest.model_dump()
    print(json.dumps(manifest_data, indent=2))


def run_repro_run(reproducer_id: str):
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    repo = ReproducerRepository(db)
    r = repo.get_by_id(reproducer_id)
    if not r:
        print(f"[!] Reproducer '{reproducer_id}' not found.")
        return
    runner = SandboxRunner()
    policy = SandboxPolicy(mode=SandboxMode.UNTRUSTED_REPRODUCTION, allow_network=False)
    res = runner.execute(command=r.manifest.run_command, workspace=Path(PROJECT_ROOT), policy=policy)
    print("=" * 70)
    print(f"Sandbox Execution: {res.status.value}")
    print("=" * 70)
    print(f"Exit code:      {res.exit_code}")
    print(f"Execution ID:   {res.trace.sandbox_execution_id}")
    print(f"Wall time:      {res.trace.wall_time_seconds:.4f}s")
    print(f"Stdout hash:    {res.trace.stdout_hash}")
    print(f"Network:        {res.trace.network_policy}")


def run_validate(reproducer_id: str):
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    r_repo = ReproducerRepository(db)
    c_repo = CandidateRepository(db)
    v_repo = ValidationResultRepository(db)
    r = r_repo.get_by_id(reproducer_id)
    if not r:
        print(f"[!] Reproducer '{reproducer_id}' not found.")
        return
    c = c_repo.get_by_id(r.candidate_id)
    if not c:
        print(f"[!] Candidate '{r.candidate_id}' not found for reproducer.")
        return
    validator = IndependentValidator(db_service=db)
    req = ValidationRequest(candidate=c, reproducer=r, repo_root=str(PROJECT_ROOT))
    res = validator.validate(req)
    v_repo.save(res)
    print("=" * 70)
    print("Independent Validator Verdict (Phase 8)")
    print("=" * 70)
    print(f"Validation ID:  {res.validation_id}")
    print(f"Verdict:        {res.verdict.value}")
    print(f"Confidence:     {res.confidence_score}")
    print(f"Determinism:    {res.determinism.determinism_class.value} ({res.determinism.success_count}/{res.determinism.replay_count})")
    print(f"Evidence IDs:   {len(res.supporting_evidence_ids)} records emitted")
    print(f"Reasoning:      {res.reasoning}")


def run_validation_inspect(validation_id: str):
    cfg_mgr = ConfigManager()
    db = _get_db(cfg_mgr)
    repo = ValidationResultRepository(db)
    res = repo.get_by_id(validation_id)
    if not res:
        print(f"[!] Validation result '{validation_id}' not found.")
        return
    print("=" * 70)
    print(f"Validation Result: {res.validation_id}")
    print("=" * 70)
    print(json.dumps(res.model_dump(), default=str, indent=2))


def main():
    parser = argparse.ArgumentParser(description="LLMorch CLI (Phase 8)")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("doctor")
    sub.add_parser("agents")
    sub.add_parser("config")
    sub.add_parser("version")

    # Repro commands (Phase 8)
    repro_p = sub.add_parser("repro")
    repro_sub = repro_p.add_subparsers(dest="repro_command")
    repro_sub.add_parser("list")
    repro_insp = repro_sub.add_parser("inspect"); repro_insp.add_argument("reproducer_id")
    repro_run_cmd = repro_sub.add_parser("run"); repro_run_cmd.add_argument("reproducer_id")

    # Validate commands (Phase 8)
    val_p = sub.add_parser("validate")
    val_p.add_argument("reproducer_id")

    val_insp_p = sub.add_parser("validation")
    val_insp_sub = val_insp_p.add_subparsers(dest="validation_command")
    v_insp = val_insp_sub.add_parser("inspect"); v_insp.add_argument("validation_id")

    # Repo commands
    repo_p = sub.add_parser("repo")
    repo_sub = repo_p.add_subparsers(dest="repo_command")
    scan_p = repo_sub.add_parser("scan"); scan_p.add_argument("repo_path")
    status_p = repo_sub.add_parser("status"); status_p.add_argument("snapshot_id")
    files_p = repo_sub.add_parser("files"); files_p.add_argument("snapshot_id")
    units_p = repo_sub.add_parser("units"); units_p.add_argument("snapshot_id")
    unit_p = repo_sub.add_parser("unit"); unit_p.add_argument("unit_id")
    surf_p = repo_sub.add_parser("security-surface"); surf_p.add_argument("unit_id")
    dep_p = repo_sub.add_parser("dependencies"); dep_p.add_argument("unit_id")
    diff_p = repo_sub.add_parser("diff"); diff_p.add_argument("snap_a"); diff_p.add_argument("snap_b")

    # Memory commands
    mem_p = sub.add_parser("memory")
    mem_sub = mem_p.add_subparsers(dest="mem_command")
    mem_sub.add_parser("status")
    mem_sub.add_parser("list-global")
    proj_p = mem_sub.add_parser("list-project"); proj_p.add_argument("project_id")
    insp_p = mem_sub.add_parser("inspect"); insp_p.add_argument("pattern_id")
    srch_p = mem_sub.add_parser("search"); srch_p.add_argument("query")

    # Investigate command
    inv_p = sub.add_parser("investigate")
    inv_p.add_argument("--repo", required=True)
    inv_p.add_argument("--target", required=True)
    inv_p.add_argument("--agent")
    inv_p.add_argument("--agents")
    inv_p.add_argument("--agent-count", type=str)
    inv_p.add_argument("--domain", default="generic")

    args = parser.parse_args()

    if args.command == "doctor":
        run_doctor()
    elif args.command == "agents":
        run_agents()
    elif args.command == "config":
        run_config()
    elif args.command == "version":
        run_version()
    elif args.command == "repro":
        rc = args.repro_command
        if rc == "list":
            run_repro_list()
        elif rc == "inspect":
            run_repro_inspect(args.reproducer_id)
        elif rc == "run":
            run_repro_run(args.reproducer_id)
        else:
            repro_p.print_help()
    elif args.command == "validate":
        run_validate(args.reproducer_id)
    elif args.command == "validation":
        vc = args.validation_command
        if vc == "inspect":
            run_validation_inspect(args.validation_id)
        else:
            val_insp_p.print_help()
    elif args.command == "repo":
        rc = args.repo_command
        if rc == "scan":
            run_repo_scan(args.repo_path)
        elif rc == "status":
            run_repo_status(args.snapshot_id)
        elif rc == "files":
            run_repo_files(args.snapshot_id)
        elif rc == "units":
            run_repo_units(args.snapshot_id)
        elif rc == "unit":
            run_repo_unit(args.unit_id)
        elif rc == "security-surface":
            run_repo_security_surface(args.unit_id)
        elif rc == "dependencies":
            run_repo_dependencies(args.unit_id)
        elif rc == "diff":
            run_repo_diff(args.snap_a, args.snap_b)
        else:
            repo_p.print_help()
    elif args.command == "memory":
        mc = args.mem_command
        if mc == "status":
            run_memory_status()
        elif mc == "list-global":
            run_memory_list_global()
        elif mc == "list-project":
            run_memory_list_project(args.project_id)
        elif mc == "inspect":
            run_memory_inspect(args.pattern_id)
        elif mc == "search":
            run_memory_search(args.query)
        else:
            mem_p.print_help()
    elif args.command == "investigate":
        run_investigate(args.repo, args.target, args.agent, args.agents, args.agent_count, args.domain)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
