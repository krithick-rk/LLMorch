"""
LLMorch Repository Intelligence - AnalysisUnit Builder (Phase 7)
Constructs first-class AnalysisUnit objects from classified repository files,
symbols, build targets, dependency edges, and security surface information.
"""

import os
import hashlib
from typing import List, Dict, Optional
from pathlib import Path

from schemas.analysis_unit import AnalysisUnit, AnalysisUnitType, PriorityLevel
from schemas.file_classification import FileClassificationRecord, FileClassificationType
from schemas.repository_intelligence import BuildTarget, SymbolEntity, DependencyRelation, HW_SW_Contract
from schemas.security_surface import SecuritySurface
from repository_intelligence.relevance import RelevanceEngine
from repository_intelligence.dependency_graph import DependencyGraphEngine


class AnalysisUnitBuilder:
    """
    Constructs meaningful AnalysisUnit objects that correspond to
    real security boundaries — NOT one-file-per-unit.
    """

    @classmethod
    def build_units(
        cls,
        repository_id: str,
        snapshot_id: str,
        file_records: List[FileClassificationRecord],
        symbols: List[SymbolEntity],
        build_targets: List[BuildTarget],
        contracts: List[HW_SW_Contract],
        dependencies: List[DependencyRelation],
        security_surface: Optional[SecuritySurface] = None,
    ) -> List[AnalysisUnit]:
        units: List[AnalysisUnit] = []

        # Group files by language/domain (content-bearing files only)
        domain_map: Dict[str, List[FileClassificationRecord]] = {}
        for rec in file_records:
            if rec.size_bytes > 0 and rec.classification in (
                FileClassificationType.PRIMARY_SOURCE,
                FileClassificationType.SECURITY_METADATA,
                FileClassificationType.FORMAL
            ):
                domain_map.setdefault(rec.language, []).append(rec)

        # 1. RTL Modules as AnalysisUnits (module-cluster boundary)
        rtl_files = [r for r in domain_map.get("systemverilog", []) + domain_map.get("verilog", []) + domain_map.get("sva", [])]
        if rtl_files:
            rtl_syms = [s for s in symbols if s.kind == "module" and s.language == "rtl"]
            for sym in rtl_syms[:20]:  # cap at 20 module units
                scoped_files = [r.rel_path for r in rtl_files if sym.file_path in r.rel_path or r.rel_path == sym.file_path]
                unit = AnalysisUnit(
                    repository_id=repository_id,
                    snapshot_id=snapshot_id,
                    unit_type=AnalysisUnitType.RTL_BLOCK,
                    domain="rtl",
                    name=f"RTL Module: {sym.name}",
                    description=f"RTL module {sym.name} extracted from {sym.file_path}",
                    anchors=[sym.name],
                    source_files=scoped_files,
                    symbols=[sym.symbol_id],
                    trust_boundaries=["RTL hardware isolation boundary"],
                    security_properties=["Register write path requires privilege check"],
                    classification="PRIMARY_SOURCE",
                    provenance={"extractor": "AnalysisUnitBuilder", "method": "rtl_module_cluster"}
                )
                if security_surface:
                    unit.assets = [a.name for a in security_surface.assets if sym.name in a.name]
                    unit.countermeasures = [cm.name for cm in security_surface.countermeasures if sym.name in cm.name]
                units.append(unit)

        # 2. Bazel Targets as AnalysisUnits
        for bt in build_targets[:30]:  # cap at 30
            unit = AnalysisUnit(
                repository_id=repository_id,
                snapshot_id=snapshot_id,
                unit_type=AnalysisUnitType.BAZEL_TARGET,
                domain="c_cpp" if "cc_" in bt.build_system.lower() else bt.build_system.lower(),
                name=f"Build Target: {bt.target_name}",
                description=f"{bt.build_system} target '{bt.target_name}' in {bt.defined_in_file}",
                anchors=[bt.target_name],
                source_files=bt.source_files,
                build_targets=[bt.target_id],
                dependencies=bt.dependencies,
                classification="BUILD_METADATA",
                provenance={"extractor": "AnalysisUnitBuilder", "method": "bazel_target"}
            )
            units.append(unit)

        # 3. HW-SW Contract AnalysisUnits
        for contract in contracts[:15]:
            refs = [r for r in [contract.hjson_ref, contract.header_ref, contract.dif_ref] if r]
            unit = AnalysisUnit(
                repository_id=repository_id,
                snapshot_id=snapshot_id,
                unit_type=AnalysisUnitType.HW_SW_CONTRACT,
                domain="hw_sw",
                name=f"HW-SW Contract: {contract.register_name}",
                description=f"HW↔SW register contract for {contract.register_name}: HJSON→header→DIF",
                anchors=[contract.register_name],
                source_files=refs,
                assets=[contract.register_name],
                trust_boundaries=["HW-SW privilege boundary"],
                security_properties=[f"Register {contract.register_name} access policy: {contract.access_policy}"],
                countermeasures=[f"Lock bits: {contract.lock_bits}"],
                classification="SECURITY_METADATA",
                provenance={"extractor": "AnalysisUnitBuilder", "method": "hw_sw_contract"}
            )
            units.append(unit)

        # 4. Python / Go / Java / C++ Package-Level AnalysisUnits (group by directory)
        for lang in ("python", "go", "java", "c", "cpp"):
            lang_files = domain_map.get(lang, [])
            if not lang_files:
                continue

            dir_map: Dict[str, List[str]] = {}
            for rec in lang_files:
                dir_key = os.path.dirname(rec.rel_path) or "root"
                dir_map.setdefault(dir_key, []).append(rec.rel_path)

            for dir_key, paths in list(dir_map.items())[:10]:
                lang_syms = [s.symbol_id for s in symbols if s.language == lang and any(p in s.file_path for p in paths)]
                unit = AnalysisUnit(
                    repository_id=repository_id,
                    snapshot_id=snapshot_id,
                    unit_type=AnalysisUnitType.MODULE,
                    domain=lang,
                    name=f"{lang.upper()} Package: {dir_key}",
                    description=f"Language package/directory group: {dir_key} ({len(paths)} files)",
                    anchors=[dir_key],
                    source_files=paths,
                    symbols=lang_syms,
                    classification="PRIMARY_SOURCE",
                    provenance={"extractor": "AnalysisUnitBuilder", "method": f"{lang}_package_group"}
                )
                units.append(unit)

        # Apply Relevance Scoring to all units
        scored: List[AnalysisUnit] = []
        for unit in units:
            unit, reasons = RelevanceEngine.score_unit(unit)
            unit.provenance["relevance_reasons"] = reasons
            scored.append(unit)

        # Sort by relevance_score DESC
        scored.sort(key=lambda u: u.relevance_score, reverse=True)
        return scored
