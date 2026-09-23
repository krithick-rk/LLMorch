"""
LLMorch Repository Intelligence - Scoped Agent Context Generator (Phase 7)
Produces focused, secret-free, vendor-free agent contexts from AnalysisUnits.
Supports controlled 1-hop context expansion with full audit provenance.
"""

from typing import List, Dict, Any, Optional
from schemas.analysis_unit import AnalysisUnit, PriorityLevel
from schemas.file_classification import FileClassificationRecord, FileClassificationType
from schemas.repository_intelligence import ContextExpansionRecord, DependencyRelation
from schemas.security_surface import SecuritySurface
from schemas.memory import MemoryRetrievalRecord


class AgentContextGenerator:
    """
    Builds scoped agent investigation context from AnalysisUnit + supporting data.
    Enforces:
    - No secrets in context
    - No vendor code in context by default
    - No generated code in context by default
    - Controlled 1-hop expansion with audit
    """

    SECRET_CLASSIFICATIONS = {
        FileClassificationType.SECRET,
        FileClassificationType.NOISE,
        FileClassificationType.BUILD_OUTPUT,
        FileClassificationType.CACHE,
    }

    DEFAULT_EXCLUDED_CLASSIFICATIONS = {
        FileClassificationType.VENDOR,
        FileClassificationType.THIRD_PARTY,
        FileClassificationType.GENERATED,
        FileClassificationType.CACHE,
        FileClassificationType.BUILD_OUTPUT,
        FileClassificationType.NOISE,
        FileClassificationType.SECRET,
    }

    @classmethod
    def build_context(
        cls,
        unit: AnalysisUnit,
        all_files: List[FileClassificationRecord],
        security_surface: Optional[SecuritySurface],
        memory_matches: List[MemoryRetrievalRecord],
        cheap_findings: List[str],
        expand_hops: int = 0,
        expansion_reason: Optional[str] = None,
        requesting_agent_id: str = "orchestrator",
        dependencies: Optional[List[DependencyRelation]] = None,
    ) -> Dict[str, Any]:
        """
        Generates a scoped context payload for an agent.
        Excludes secrets, vendor code, and generated code unless explicitly expanded.
        """
        file_map = {r.rel_path: r for r in all_files}
        included: List[str] = []
        excluded: List[str] = []

        # Step 1: Include primary unit source files (filtered)
        for path in unit.source_files:
            rec = file_map.get(path)
            if rec and rec.classification in cls.SECRET_CLASSIFICATIONS:
                excluded.append(path)
            elif rec and rec.classification in cls.DEFAULT_EXCLUDED_CLASSIFICATIONS:
                excluded.append(path)
            else:
                included.append(path)

        # Step 2: 1-Hop Context Expansion (controlled)
        expansion_record: Optional[ContextExpansionRecord] = None
        if expand_hops >= 1 and dependencies:
            dep_targets = {
                d.target_id for d in dependencies if d.source_id in unit.source_files
            } | {
                d.source_id for d in dependencies if d.target_id in unit.source_files
            }
            new_paths = []
            for path in dep_targets:
                if path not in included:
                    rec = file_map.get(path)
                    if rec and rec.classification not in cls.DEFAULT_EXCLUDED_CLASSIFICATIONS:
                        new_paths.append(path)
                        included.append(path)
                    else:
                        excluded.append(path)

            if new_paths:
                expansion_record = ContextExpansionRecord(
                    analysis_unit_id=unit.analysis_unit_id,
                    requesting_agent_id=requesting_agent_id,
                    reason=expansion_reason or "1-hop dependency expansion requested",
                    expanded_paths=new_paths,
                    status="ALLOWED"
                )

        # Step 3: Update unit context tracking
        unit.included_context = included
        unit.excluded_context = excluded
        if expansion_record:
            unit.expansion_reason = expansion_record.reason

        # Step 4: Memory pattern context
        memory_context_lines = []
        for mem in memory_matches:
            memory_context_lines.append(
                f"- [Pattern {mem.pattern_id}] {mem.pattern.title} (match={mem.match_type.value}, score={mem.match_score})"
            )

        # Step 5: Security surface summary
        surf_summary = ""
        if security_surface:
            surf_summary = (
                f"Assets: {[a.name for a in security_surface.assets]}\n"
                f"Entry Points: {[e.name for e in security_surface.entry_points]}\n"
                f"Countermeasures: {[cm.name for cm in security_surface.countermeasures]}\n"
                f"Properties: {security_surface.properties}"
            )

        return {
            "analysis_unit_id": unit.analysis_unit_id,
            "unit_name": unit.name,
            "unit_type": unit.unit_type.value,
            "domain": unit.domain,
            "description": unit.description,
            "priority": unit.priority.value,
            "relevance_score": unit.relevance_score,
            "anchors": unit.anchors,
            "included_files": included,
            "excluded_files": excluded,
            "security_surface_summary": surf_summary,
            "memory_patterns": memory_context_lines or ["No matching global patterns retrieved."],
            "cheap_deterministic_findings": cheap_findings,
            "expansion": expansion_record.model_dump() if expansion_record else None,
            "provenance": {
                "snapshot_id": unit.snapshot_id,
                "repository_id": unit.repository_id,
                "unit_provenance": unit.provenance,
            }
        }
