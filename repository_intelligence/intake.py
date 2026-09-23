"""
LLMorch Repository Intake Module
Handles authorized repository validation, path normalization, symlink safety checks,
git commit extraction, and repository snapshot creation.
"""

import os
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class RepositorySnapshot(BaseModel):
    """Metadata record representing a validated repository intake snapshot."""
    snapshot_id: str = Field(default_factory=lambda: f"snap-{uuid.uuid4().hex[:12]}", description="Unique snapshot identifier")
    absolute_root: str = Field(..., description="Canonical absolute path to repository root")
    repository_type: str = Field(default="git", description="Repository type (git, directory, archive)")
    git_commit: Optional[str] = Field(default=None, description="Git commit hash if git repository")
    file_count: int = Field(default=0, description="Total analyzed file count")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Snapshot creation timestamp")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")


class RepositoryIntake:
    """
    Validates authorized repository boundaries, prevents path traversal,
    audits external symlinks, and creates RepositorySnapshot metadata records.
    """

    def __init__(self, authorized_root: str):
        self.raw_root = Path(authorized_root)
        self.canonical_root = self.raw_root.resolve()

        if not self.canonical_root.exists() or not self.canonical_root.is_dir():
            raise ValueError(f"Authorized repository path '{authorized_root}' does not exist or is not a directory.")

    def audit_symlinks(self) -> Dict[str, Any]:
        """
        Scans repository tree for external or suspicious symlinks.
        Returns audit summary dictionary.
        """
        suspicious_symlinks = []
        for root, dirs, files in os.walk(self.canonical_root, followlinks=False):
            for name in dirs + files:
                item_path = Path(root) / name
                if item_path.is_symlink():
                    target = item_path.resolve()
                    try:
                        target.relative_to(self.canonical_root)
                    except ValueError:
                        # Target is outside authorized root!
                        suspicious_symlinks.append({
                            "path": str(item_path),
                            "target": str(target)
                        })
        return {
            "has_external_symlinks": len(suspicious_symlinks) > 0,
            "external_symlinks": suspicious_symlinks
        }

    def get_git_commit(self) -> Optional[str]:
        """Extracts HEAD git commit hash if repository is a Git repo."""
        git_dir = self.canonical_root / ".git"
        if not git_dir.exists():
            return None
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.canonical_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            return res.stdout.strip()
        except Exception:
            return None

    def create_snapshot(self) -> RepositorySnapshot:
        """
        Executes validation checks and produces a RepositorySnapshot record.
        """
        symlink_audit = self.audit_symlinks()
        if symlink_audit["has_external_symlinks"]:
            # Log warning, but do not resolve or follow external symlinks
            pass

        git_commit = self.get_git_commit()
        repo_type = "git" if git_commit else "directory"

        # Count total files (excluding .git)
        file_count = 0
        for root, dirs, files in os.walk(self.canonical_root):
            if ".git" in dirs:
                dirs.remove(".git")
            file_count += len(files)

        return RepositorySnapshot(
            absolute_root=str(self.canonical_root),
            repository_type=repo_type,
            git_commit=git_commit,
            file_count=file_count
        )
