"""
LLMorch Repository Intelligence - Central Service & Query API (Phase 7)
Orchestrates the full repository intelligence pipeline and exposes a clean query interface.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from schemas.analysis_unit import AnalysisUnit, PriorityLevel
from schemas.security_surface import SecuritySurface
from schemas.file_classification import FileClassificationRecord, FileClassificationType
from schemas.repository_intelligence import (
    ExtendedRepositorySnapshot, BuildTarget, SymbolEntity,
    DependencyRelation, HW_SW_Contract, SecretQuarantineRecord, ContextExpansionRecord,
)
from schemas.event import Event, EventType

from repository_intelligence.scanner import RepositoryTreeScanner
from repository_intelligence.build_system import BuildSystemIndexer
from repository_intelligence.symbol_extractor import SymbolExtractor
from repository_intelligence.dependency_graph import DependencyGraphEngine
from repository_intelligence.security_surface_builder import SecuritySurfaceBuilder
from repository_intelligence.analysis_unit_builder import AnalysisUnitBuilder
from repository_intelligence.context import AgentContextGenerator

from history.database import DatabaseService
from history.repositories import (
    ExtendedRepositorySnapshotRepository,
    SourceFileRepository,
    AnalysisUnitRepository,
    SecuritySurfaceRepository,
    SecretQuarantineRepository,
    EventRepository,
)

logger = logging.getLogger(__name__)


class RepositoryIntelligenceService:
    """
    Central Repository Intelligence Pipeline Manager and Query API.

    Pipeline:
      Repository → Snapshot → Classification → Secrets Quarantine → Symlink Safety
      → Build Indexing → Symbol Extraction → Dependency Graph → Security Surface
      → AnalysisUnit Construction → Relevance Ranking → Scoped Context Generation

    Query API:
      get_snapshot(), get_analysis_units(), get_unit(), get_security_surface(),
      get_dependencies(), expand_context(), diff_snapshots()
    """

    def __init__(self, db_service: DatabaseService):
        self.db = db_service
        self.snap_repo = ExtendedRepositorySnapshotRepository(self.db)
        self.file_repo = SourceFileRepository(self.db)
        self.unit_repo = AnalysisUnitRepository(self.db)
        self.surf_repo = SecuritySurfaceRepository(self.db)
        self.secret_repo = SecretQuarantineRepository(self.db)
        self.event_repo = EventRepository(self.db)

        # In-memory cache for current pipeline run
        self._snapshot: Optional[ExtendedRepositorySnapshot] = None
        self._file_records: List[FileClassificationRecord] = []
        self._build_targets: List[BuildTarget] = []
        self._symbols: List[SymbolEntity] = []
        self._dependencies: List[DependencyRelation] = []
        self._contracts: List[HW_SW_Contract] = []
        self._security_surface: Optional[SecuritySurface] = None
        self._analysis_units: List[AnalysisUnit] = []
        self._secrets: List[SecretQuarantineRecord] = []

    def scan_repository(self, repo_path: str) -> ExtendedRepositorySnapshot:
        """
        Executes full Phase 7 repository intelligence pipeline.
        """
        self.event_repo.record(Event(
            event_type=EventType.REPOSITORY_SCAN_STARTED,
            actor="repository_intelligence",
            payload={"repo_path": repo_path}
        ))

        # Layer 1: Snapshot + File Classification + Symlink Safety + Secret Quarantine
        scanner = RepositoryTreeScanner(repo_path)
        snapshot, file_records, symlinks, secrets = scanner.scan()
        self._snapshot = snapshot
        self._file_records = file_records
        self._secrets = secrets

        # Persist snapshot and file records
        self.snap_repo.save(snapshot)
        self.file_repo.save_batch(file_records, snapshot.snapshot_id)

        # Emit classified file events
        for rec in file_records[:100]:  # cap bulk events
            self.event_repo.record(Event(
                event_type=EventType.FILE_CLASSIFIED,
                actor="repository_intelligence",
                payload={"rel_path": rec.rel_path, "classification": rec.classification.value}
            ))

        # Quarantine secrets
        for sec in secrets:
            self.secret_repo.save(sec, snapshot_id=snapshot.snapshot_id)
            self.event_repo.record(Event(
                event_type=EventType.SECRET_QUARANTINED,
                actor="repository_intelligence",
                payload={"file_path": sec.file_path, "secret_type": sec.secret_type}
            ))

        # Block external symlinks
        for sl in symlinks:
            if sl.is_external:
                self.event_repo.record(Event(
                    event_type=EventType.SYMLINK_BLOCKED,
                    actor="repository_intelligence",
                    payload={"symlink_path": sl.symlink_path, "target": sl.target_path}
                ))

        # Layer 3: Build System Intelligence
        self._build_targets = BuildSystemIndexer.index_build_targets(file_records, repo_path)
        self._contracts = BuildSystemIndexer.extract_hw_sw_contracts(file_records, repo_path)
        for bt in self._build_targets:
            self.event_repo.record(Event(
                event_type=EventType.BUILD_TARGET_DISCOVERED,
                actor="repository_intelligence",
                payload={"target_name": bt.target_name, "build_system": bt.build_system}
            ))

        # Layer 4: Symbol / Module Intelligence
        self._symbols = SymbolExtractor.extract_symbols(file_records, repo_path)

        # Layer 5: Dependency Graph
        self._dependencies = DependencyGraphEngine.build_dependency_graph(file_records, repo_path)
        for dep in self._dependencies[:50]:
            self.event_repo.record(Event(
                event_type=EventType.DEPENDENCY_DISCOVERED,
                actor="repository_intelligence",
                payload={"source": dep.source_id, "target": dep.target_id, "type": dep.relation_type.value}
            ))

        # Layer 6: Security Surface
        primary_files = [r for r in file_records if r.classification in (
            FileClassificationType.PRIMARY_SOURCE,
            FileClassificationType.SECURITY_METADATA,
            FileClassificationType.FORMAL
        )]
        self._security_surface = SecuritySurfaceBuilder.build_security_surface(
            analysis_unit_id="repo-level",
            repository_id=snapshot.repository_id,
            snapshot_id=snapshot.snapshot_id,
            scoped_files=primary_files,
            contracts=self._contracts
        )
        self.surf_repo.save(self._security_surface)
        self.event_repo.record(Event(
            event_type=EventType.SECURITY_SURFACE_CREATED,
            actor="repository_intelligence",
            payload={"security_surface_id": self._security_surface.security_surface_id}
        ))

        # Layer 7: AnalysisUnit Construction
        self._analysis_units = AnalysisUnitBuilder.build_units(
            repository_id=snapshot.repository_id,
            snapshot_id=snapshot.snapshot_id,
            file_records=file_records,
            symbols=self._symbols,
            build_targets=self._build_targets,
            contracts=self._contracts,
            dependencies=self._dependencies,
            security_surface=self._security_surface
        )
        for unit in self._analysis_units:
            self.unit_repo.save(unit)
            self.event_repo.record(Event(
                event_type=EventType.ANALYSIS_UNIT_CREATED,
                actor="repository_intelligence",
                payload={"unit_id": unit.analysis_unit_id, "name": unit.name, "priority": unit.priority.value}
            ))
            self.event_repo.record(Event(
                event_type=EventType.ANALYSIS_UNIT_RANKED,
                actor="repository_intelligence",
                payload={"unit_id": unit.analysis_unit_id, "relevance_score": unit.relevance_score}
            ))

        self.event_repo.record(Event(
            event_type=EventType.REPOSITORY_SCAN_COMPLETED,
            actor="repository_intelligence",
            payload={
                "snapshot_id": snapshot.snapshot_id,
                "file_count": snapshot.file_count,
                "units_created": len(self._analysis_units),
                "secrets_quarantined": len(secrets),
            }
        ))

        return snapshot

    # ── Query API ─────────────────────────────────────────────────────────────

    def get_snapshot(self, snapshot_id: str) -> Optional[ExtendedRepositorySnapshot]:
        return self.snap_repo.get(snapshot_id)

    def get_analysis_units(self, snapshot_id: Optional[str] = None) -> List[AnalysisUnit]:
        if snapshot_id:
            return self.unit_repo.list_for_snapshot(snapshot_id)
        return self._analysis_units

    def get_unit(self, analysis_unit_id: str) -> Optional[AnalysisUnit]:
        return self.unit_repo.get(analysis_unit_id)

    def get_security_surface(self, analysis_unit_id: Optional[str] = None) -> Optional[SecuritySurface]:
        return self._security_surface

    def get_dependencies(self, analysis_unit_id: str) -> List[DependencyRelation]:
        unit = self.unit_repo.get(analysis_unit_id)
        if not unit:
            return []
        return [
            d for d in self._dependencies
            if d.source_id in unit.source_files or d.target_id in unit.source_files
        ]

    def build_agent_context(
        self,
        unit: AnalysisUnit,
        memory_matches: list,
        cheap_findings: List[str],
        expand_hops: int = 0,
        expansion_reason: Optional[str] = None,
        requesting_agent_id: str = "orchestrator"
    ) -> Dict[str, Any]:
        context = AgentContextGenerator.build_context(
            unit=unit,
            all_files=self._file_records,
            security_surface=self._security_surface,
            memory_matches=memory_matches,
            cheap_findings=cheap_findings,
            expand_hops=expand_hops,
            expansion_reason=expansion_reason,
            requesting_agent_id=requesting_agent_id,
            dependencies=self._dependencies,
        )
        if expand_hops >= 1 and context.get("expansion"):
            self.event_repo.record(Event(
                event_type=EventType.CONTEXT_EXPANSION_ALLOWED,
                actor="repository_intelligence",
                payload={"unit_id": unit.analysis_unit_id, "reason": expansion_reason or "1-hop"}
            ))
        return context

    def diff_snapshots(
        self, old_snapshot: ExtendedRepositorySnapshot, new_snapshot: ExtendedRepositorySnapshot
    ) -> Dict[str, Any]:
        """Compares two snapshots; returns change signals (NEW, MODIFIED, REMOVED, UNCHANGED)."""
        old_files = {r.rel_path: r.content_hash for r in self.file_repo.list_for_snapshot(old_snapshot.snapshot_id)}
        new_files = {r.rel_path: r.content_hash for r in self.file_repo.list_for_snapshot(new_snapshot.snapshot_id)}

        new_paths = set(new_files.keys()) - set(old_files.keys())
        removed_paths = set(old_files.keys()) - set(new_files.keys())
        modified_paths = {p for p in old_files if p in new_files and old_files[p] != new_files[p]}
        unchanged_paths = {p for p in old_files if p in new_files and old_files[p] == new_files[p]}

        return {
            "old_snapshot_id": old_snapshot.snapshot_id,
            "new_snapshot_id": new_snapshot.snapshot_id,
            "new_files": sorted(new_paths),
            "removed_files": sorted(removed_paths),
            "modified_files": sorted(modified_paths),
            "unchanged_files_count": len(unchanged_paths),
            "archive_hash_changed": old_snapshot.archive_hash != new_snapshot.archive_hash,
        }
