"""
LLMorch Repository Intelligence - Dependency Graph & Reachability Engine (Phase 7)
Constructs deterministic file/module/symbol dependency graphs and computes reachability from entry points.
"""

import os
import re
from typing import List, Dict, Set, Tuple, Optional
from schemas.repository_intelligence import DependencyRelation, DependencyType, ReachabilityStatus
from schemas.file_classification import FileClassificationRecord


class DependencyGraphEngine:
    """
    Computes deterministic dependency edges and entry-point reachability hints.
    """

    @classmethod
    def build_dependency_graph(cls, file_records: List[FileClassificationRecord], repo_root: str) -> List[DependencyRelation]:
        relations: List[DependencyRelation] = []

        file_map = {r.rel_path: r for r in file_records}
        file_basenames = {os.path.basename(r.rel_path): r.rel_path for r in file_records}

        for rec in file_records:
            abs_p = rec.abs_path
            if rec.is_symlink or not os.path.exists(abs_p) or rec.size_bytes == 0:
                continue

            try:
                with open(abs_p, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(16000)

                # Includes / Imports Scan
                includes = re.findall(r'#include\s+["<]([^">]+)[">]', content)
                imports = re.findall(r'(?:import|from)\s+([A-Za-z0-9_\.]+)', content)
                sv_includes = re.findall(r'`include\s+["<]([^">]+)[">]', content)

                all_refs = includes + imports + sv_includes
                for ref in all_refs:
                    ref_base = os.path.basename(ref)
                    if ref_base in file_basenames and file_basenames[ref_base] != rec.rel_path:
                        relations.append(DependencyRelation(
                            source_id=rec.rel_path,
                            target_id=file_basenames[ref_base],
                            relation_type=DependencyType.DIRECT,
                            confidence=1.0,
                            provenance="include_import_parser"
                        ))
            except Exception:
                pass

        return relations

    @classmethod
    def compute_reachability(
        cls,
        target_path: str,
        entry_points: List[str],
        dependencies: List[DependencyRelation]
    ) -> ReachabilityStatus:
        """
        Determines reachability status from entry points using graph BFS.
        """
        if not entry_points:
            return ReachabilityStatus.POSSIBLY_REACHABLE

        if target_path in entry_points or any(ep in target_path for ep in entry_points):
            return ReachabilityStatus.REACHABLE

        adj: Dict[str, List[str]] = {}
        for edge in dependencies:
            adj.setdefault(edge.source_id, []).append(edge.target_id)
            adj.setdefault(edge.target_id, []).append(edge.source_id)

        visited: Set[str] = set()
        queue = list(entry_points)

        for ep in entry_points:
            visited.add(ep)

        depth = 0
        while queue and depth < 3:
            next_queue = []
            for node in queue:
                if node == target_path or target_path in node:
                    return ReachabilityStatus.REACHABLE if depth <= 1 else ReachabilityStatus.LIKELY_REACHABLE
                for neighbor in adj.get(node, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_queue.append(neighbor)
            queue = next_queue
            depth += 1

        return ReachabilityStatus.POSSIBLY_REACHABLE
