"""
LLMorch Repository Intelligence - Tree Scanner & Symlink Safety Gate (Phase 7)
Computes whole-repository archive identity, per-file hashes, symlink safety blocking, and secret quarantine.
"""

import os
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime

from schemas.file_classification import (
    FileClassificationType,
    FileClassificationRecord,
    SymlinkRecord,
    SymlinkStatus,
)
from schemas.repository_intelligence import (
    ExtendedRepositorySnapshot,
    SecretQuarantineRecord,
)
from repository_intelligence.classifier import FileClassifier
from repository_intelligence.intake import RepositoryIntake


class RepositoryTreeScanner:
    """
    Scans an authorized repository directory.
    Enforces external symlink safety boundaries, quarantines secrets,
    and computes deterministic per-file content hashes and whole archive identity.
    """

    def __init__(self, repo_root: str):
        self.intake = RepositoryIntake(repo_root)
        self.canonical_root = self.intake.canonical_root

    def scan(self) -> Tuple[ExtendedRepositorySnapshot, List[FileClassificationRecord], List[SymlinkRecord], List[SecretQuarantineRecord]]:
        file_records: List[FileClassificationRecord] = []
        symlink_records: List[SymlinkRecord] = []
        secret_records: List[SecretQuarantineRecord] = []

        archive_hasher = hashlib.sha256()
        lang_counts: Dict[str, int] = {}
        class_counts: Dict[str, int] = {}
        build_systems_found = set()

        for root, dirs, files in os.walk(self.canonical_root, followlinks=False):
            # Exclude .git directory
            if ".git" in dirs:
                dirs.remove(".git")

            for name in dirs + files:
                item_path = Path(root) / name

                # Symlink Audit & Safety Gate
                if item_path.is_symlink():
                    target = item_path.resolve()
                    is_ext = False
                    try:
                        target.relative_to(self.canonical_root)
                        status = SymlinkStatus.INTERNAL_VALID
                    except ValueError:
                        is_ext = True
                        status = SymlinkStatus.EXTERNAL_BLOCKED

                    symlink_records.append(SymlinkRecord(
                        symlink_path=os.path.relpath(str(item_path), str(self.canonical_root)),
                        target_path=str(target),
                        status=status,
                        is_external=is_ext
                    ))

                    if is_ext:
                        # Unsafe external symlink! Block traversal.
                        continue

            for name in files:
                abs_p = str(Path(root) / name)
                rec = FileClassifier.classify_file(abs_p, str(self.canonical_root))

                # Per-file Content Hash computation
                if not rec.is_symlink and os.path.exists(abs_p):
                    try:
                        with open(abs_p, "rb") as f:
                            c_bytes = f.read()
                            rec.content_hash = hashlib.sha256(c_bytes).hexdigest()
                            archive_hasher.update(f"{rec.rel_path}:{rec.content_hash}".encode())
                    except Exception:
                        rec.content_hash = "error_reading"

                # Secret Quarantine Check
                if rec.is_secret or rec.classification == FileClassificationType.SECRET:
                    secret_records.append(SecretQuarantineRecord(
                        file_path=rec.rel_path,
                        secret_type="CREDENTIAL_OR_SECRET",
                        redacted_preview="[REDACTED_SECRET]"
                    ))

                # Build System Tracking
                if rec.classification == FileClassificationType.BUILD_METADATA:
                    if name in {"BUILD", "BUILD.bazel", "WORKSPACE", "MODULE.bazel"}:
                        build_systems_found.add("Bazel")
                    elif name == "CMakeLists.txt":
                        build_systems_found.add("CMake")
                    elif name in {"Makefile", "makefile"}:
                        build_systems_found.add("Make")
                    elif name.endswith(".core"):
                        build_systems_found.add("FuseSoC")
                    elif name == "Cargo.toml":
                        build_systems_found.add("Cargo")

                lang_counts[rec.language] = lang_counts.get(rec.language, 0) + 1
                class_counts[rec.classification.value] = class_counts.get(rec.classification.value, 0) + 1
                file_records.append(rec)

        archive_hash = f"archive-{archive_hasher.hexdigest()[:16]}"
        git_commit = self.intake.get_git_commit()

        snapshot = ExtendedRepositorySnapshot(
            absolute_root=str(self.canonical_root),
            repository_type="git" if git_commit else "directory",
            git_commit=git_commit,
            archive_hash=archive_hash,
            file_count=len(file_records),
            language_summary=lang_counts,
            build_systems=sorted(list(build_systems_found)),
            symlink_summary={"total": len(symlink_records), "external_blocked": sum(1 for s in symlink_records if s.is_external)},
            classification_summary=class_counts
        )

        return snapshot, file_records, symlink_records, secret_records
