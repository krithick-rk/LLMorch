"""
LLMorch Correlation Engine (Phase 3/4 Multi-Agent Independent Result Correlator)
Classifies relationships across independent agent task outputs: DUPLICATE, RELATED, INDEPENDENT, CONTRADICTORY, UNRELATED.
Handles 2+ agents by comparing all pairs and aggregating into clusters.
Note: Correlator classifies relationship and preserves multi-agent discovery lineage without
acting as technical validator or consensus voter.
"""

import json
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import uuid
import hashlib

from schemas.task_result import TaskResult
from schemas.evidence import Evidence


class CorrelationType(str, Enum):
    DUPLICATE = "DUPLICATE"
    RELATED = "RELATED"
    INDEPENDENT = "INDEPENDENT"
    CONTRADICTORY = "CONTRADICTORY"
    UNRELATED = "UNRELATED"


class FindingCluster(BaseModel):
    cluster_id: str = Field(default_factory=lambda: f"cluster-{uuid.uuid4().hex[:12]}")
    classification: CorrelationType
    summary_hypothesis: str
    lineages: List[Dict[str, Any]] = Field(default_factory=list, description="Independent agent discovery lineages")
    locations: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)


class CorrelationResult(BaseModel):
    clusters: List[FindingCluster] = Field(default_factory=list)
    duplicate_count: int = 0
    related_count: int = 0
    independent_count: int = 0
    contradictory_count: int = 0
    unrelated_count: int = 0


class FindingCorrelator:
    """
    Independent Result Correlation Engine.
    Combines outputs from 1-4 independent agent runs post-discovery.
    Does NOT vote on validity — it only classifies inter-agent relationships.
    """

    @staticmethod
    def _classify_pair(res_a: Dict, res_b: Dict) -> CorrelationType:
        """Classifies the relationship between two independent agent results."""
        t_a: TaskResult = res_a["task_result"]
        t_b: TaskResult = res_b["task_result"]

        locs_a = {l.get("file_path") for l in t_a.affected_locations if isinstance(l, dict) and "file_path" in l}
        locs_b = {l.get("file_path") for l in t_b.affected_locations if isinstance(l, dict) and "file_path" in l}

        common_locs = locs_a & locs_b
        hyp_a = t_a.hypothesis.lower()
        hyp_b = t_b.hypothesis.lower()

        if hyp_a == hyp_b and common_locs:
            return CorrelationType.DUPLICATE
        if ("no vulnerability" in hyp_a and "vulnerability" in hyp_b) or \
           ("vulnerability" in hyp_a and "no vulnerability" in hyp_b):
            return CorrelationType.CONTRADICTORY
        if common_locs or any(word in hyp_b for word in hyp_a.split() if len(word) > 4):
            return CorrelationType.RELATED
        return CorrelationType.INDEPENDENT

    @staticmethod
    def correlate_results(results: List[Dict[str, Any]], evidences: List[Evidence]) -> CorrelationResult:
        """
        Correlates N independent agent TaskResult dicts and associated Evidence records.
        Supports 1, 2, 3, or 4 agent results.
        """
        if not results:
            return CorrelationResult()

        ev_ids = [e.evidence_id for e in evidences]

        # Single agent — trivially independent (no peer to compare)
        if len(results) == 1:
            res = results[0]
            task_res: TaskResult = res["task_result"]
            cluster = FindingCluster(
                classification=CorrelationType.INDEPENDENT,
                summary_hypothesis=task_res.hypothesis,
                lineages=[{"agent_id": res["agent_id"], "run_id": res["run_id"], "hypothesis": task_res.hypothesis}],
                locations=task_res.affected_locations,
                evidence_ids=ev_ids
            )
            return CorrelationResult(clusters=[cluster], independent_count=1)

        # Multi-agent: compare all pairs, pick most significant classification
        # Precedence: CONTRADICTORY > DUPLICATE > RELATED > INDEPENDENT > UNRELATED
        precedence = {
            CorrelationType.CONTRADICTORY: 5,
            CorrelationType.DUPLICATE: 4,
            CorrelationType.RELATED: 3,
            CorrelationType.INDEPENDENT: 2,
            CorrelationType.UNRELATED: 1,
        }

        overall_class = CorrelationType.INDEPENDENT
        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                pair_class = FindingCorrelator._classify_pair(results[i], results[j])
                if precedence[pair_class] > precedence[overall_class]:
                    overall_class = pair_class

        # Collect all lineages and locations
        lineages = [
            {"agent_id": r["agent_id"], "run_id": r["run_id"], "hypothesis": r["task_result"].hypothesis}
            for r in results
        ]

        all_locations_json = {
            json.dumps(l, sort_keys=True)
            for r in results
            for l in r["task_result"].affected_locations
        }
        parsed_locs = [json.loads(l) for l in all_locations_json]

        # Build summary
        if overall_class == CorrelationType.CONTRADICTORY:
            summary = f"Contradiction across {len(results)} agents: " + \
                      " vs ".join(f"'{r['task_result'].hypothesis[:60]}'" for r in results[:2])
        else:
            summary = results[0]["task_result"].hypothesis

        cluster = FindingCluster(
            classification=overall_class,
            summary_hypothesis=summary,
            lineages=lineages,
            locations=parsed_locs,
            evidence_ids=ev_ids
        )

        counts = {c: 0 for c in ["duplicate_count", "related_count", "independent_count", "contradictory_count", "unrelated_count"]}
        counts[f"{overall_class.value.lower()}_count"] = 1

        return CorrelationResult(clusters=[cluster], **counts)
