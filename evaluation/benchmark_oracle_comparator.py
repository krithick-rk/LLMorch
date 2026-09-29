"""
LLMorch — Benchmark Evaluation & Oracle Comparator
Compares discovered candidates against known ground-truth benchmark vulnerabilities
WITHOUT exposing the oracle content to the agent or reasoning engine during analysis.

Evaluates:
- In-scope vs. out-of-scope identification
- Substantive vulnerability matching (file, function, CWE, root cause, property)
- Cross-component context escalation accuracy (requires_parent_context)
"""

from __future__ import annotations

import os
import yaml
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel


class VulnerabilityMatch(BaseModel):
    benchmark_id: str
    benchmark_title: str
    benchmark_file: str
    is_in_scope: bool
    is_cross_component: bool
    matched_finding_id: Optional[str] = None
    matched_finding_title: Optional[str] = None
    matched_location: Optional[str] = None
    score: float = 0.0
    matched: bool = False
    context_escalation_correct: bool = False


class BenchmarkEvaluationReport(BaseModel):
    benchmark_name: str
    target_scope: str
    total_oracle_vulnerabilities: int
    in_scope_vulnerabilities_count: int
    out_of_scope_vulnerabilities_count: int
    discovered_findings_count: int
    matched_in_scope_count: int
    matched_in_scope_percentage: float
    context_escalation_accuracy: float
    matches: List[VulnerabilityMatch]
    unmatched_in_scope: List[str]
    unmatched_findings: List[str]


def load_benchmark_oracle(oracle_path: str = "/home/hackdac/Documents/caliptra-vuln-known-report/vulnerabilities.yaml") -> List[Dict[str, Any]]:
    p = Path(oracle_path)
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("vulnerabilities", [])


def evaluate_findings_against_benchmark(
    discovered_findings: List[Dict[str, Any]],
    target_scope: str = "runtime",
    oracle_path: str = "/home/hackdac/Documents/caliptra-vuln-known-report/vulnerabilities.yaml"
) -> BenchmarkEvaluationReport:
    """
    Evaluates discovered findings against the benchmark oracle independently.
    """
    oracle_vulns = load_benchmark_oracle(oracle_path)
    
    matches: List[VulnerabilityMatch] = []
    in_scope_matched = 0
    in_scope_total = 0
    context_correct_count = 0
    
    matched_finding_ids = set()

    for ov in oracle_vulns:
        b_id = ov.get("id")
        b_title = ov.get("title")
        b_file = ov.get("file", "")
        b_cwe = ov.get("cwe", "").lower()
        is_cross = ov.get("is_cross_component", False)
        
        # Check if in scope of the analyzed directory
        is_in_scope = (target_scope in b_file or b_file.startswith(target_scope))
        if is_in_scope:
            in_scope_total += 1

        best_score = 0.0
        best_finding = None

        for f in discovered_findings:
            locs_str = f.get("locations") or "[]"
            locs = json.loads(locs_str) if isinstance(locs_str, str) else locs_str
            lineage = json.loads(f.get("lineage") or "{}") if isinstance(f.get("lineage"), str) else f.get("lineage", {})
            f_file = locs[0].get("file", "") if locs else ""
            f_hypo = (f.get("hypothesis") or "").lower()
            f_title = (lineage.get("title") or f.get("notes") or "").lower()

            # Compare file path component
            b_basename = Path(b_file).name
            score = 0.0
            if b_basename and b_basename in f_file:
                score += 0.4
            
            # Compare symbol or keywords in title / hypothesis
            b_words = [w.lower() for w in ov.get("title", "").split() if len(w) > 3]
            kw_hits = sum(1 for w in b_words if w in f_hypo or w in f_title)
            score += min(0.4, (kw_hits / max(1, len(b_words))) * 0.6)

            # Compare CWE / property
            if any(part in f_hypo or part in f_title for part in b_cwe.split()):
                score += 0.2

            if score > best_score:
                best_score = score
                best_finding = f

        is_matched = best_score >= 0.5
        matched_f_id = best_finding.get("finding_id") if (is_matched and best_finding) else None
        matched_f_title = best_finding.get("hypothesis") if (is_matched and best_finding) else None
        
        # Check context escalation correctness
        context_escalation_ok = False
        if best_finding:
            f_lineage = json.loads(best_finding.get("lineage") or "{}") if isinstance(best_finding.get("lineage"), str) else best_finding.get("lineage", {})
            f_req_ctx = f_lineage.get("requires_parent_context", False)
            if is_cross == f_req_ctx:
                context_escalation_ok = True
                context_correct_count += 1

        if is_in_scope and is_matched:
            in_scope_matched += 1
            if matched_f_id:
                matched_finding_ids.add(matched_f_id)

        vm = VulnerabilityMatch(
            benchmark_id=b_id,
            benchmark_title=b_title,
            benchmark_file=b_file,
            is_in_scope=is_in_scope,
            is_cross_component=is_cross,
            matched_finding_id=matched_f_id,
            matched_finding_title=matched_f_title,
            matched_location=b_file if is_matched else None,
            score=round(best_score, 2),
            matched=is_matched,
            context_escalation_correct=context_escalation_ok
        )
        matches.append(vm)

    unmatched_in = [m.benchmark_id for m in matches if m.is_in_scope and not m.matched]
    unmatched_f = [f.get("finding_id") for f in discovered_findings if f.get("finding_id") not in matched_finding_ids]

    in_scope_pct = (in_scope_matched / max(1, in_scope_total)) * 100.0
    context_acc = (context_correct_count / max(1, len(oracle_vulns))) * 100.0

    return BenchmarkEvaluationReport(
        benchmark_name="Caliptra Known Vulnerability Benchmark",
        target_scope=target_scope,
        total_oracle_vulnerabilities=len(oracle_vulns),
        in_scope_vulnerabilities_count=in_scope_total,
        out_of_scope_vulnerabilities_count=len(oracle_vulns) - in_scope_total,
        discovered_findings_count=len(discovered_findings),
        matched_in_scope_count=in_scope_matched,
        matched_in_scope_percentage=round(in_scope_pct, 1),
        context_escalation_accuracy=round(context_acc, 1),
        matches=matches,
        unmatched_in_scope=unmatched_in,
        unmatched_findings=unmatched_f
    )


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
    from history.database import DatabaseService, get_db_path
    db = DatabaseService(get_db_path())
    with db.get_connection() as conn:
        rows = conn.execute("SELECT * FROM findings").fetchall()
        findings_data = [dict(r) for r in rows]

    report = evaluate_findings_against_benchmark(findings_data, target_scope="runtime")
    print(f"=== BENCHMARK EVALUATION ORACLE REPORT ===")
    print(f"Benchmark: {report.benchmark_name}")
    print(f"Scope: {report.target_scope}")
    print(f"Total Oracle Vulnerabilities: {report.total_oracle_vulnerabilities}")
    print(f"In-Scope Vulnerabilities: {report.in_scope_vulnerabilities_count}")
    print(f"Discovered Findings: {report.discovered_findings_count}")
    print(f"Matched In-Scope: {report.matched_in_scope_count}/{report.in_scope_vulnerabilities_count} ({report.matched_in_scope_percentage}%)")
    print("\nMatches:")
    for m in report.matches:
        if m.is_in_scope:
            status = f"✓ MATCH ({m.matched_finding_id})" if m.matched else "✗ MISSED"
            ctx_str = " [CONTEXT REQ]" if m.is_cross_component else " [LOCAL]"
            print(f"  {m.benchmark_id}: {m.benchmark_title}{ctx_str} -> {status}")
