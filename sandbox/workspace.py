"""
LLMorch Workspace Management Module
Manages isolated task worktree/directory setup and process isolation environments.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class Workspace(BaseModel):
    """Metadata record for a task workspace."""
    workspace_id: str = Field(default_factory=lambda: f"ws-{uuid.uuid4().hex[:12]}", description="Unique workspace identifier")
    workflow_id: str = Field(..., description="Parent workflow identifier")
    task_id: str = Field(..., description="Target task identifier")
    working_directory: str = Field(..., description="Absolute path to isolated workspace working directory")
    is_git_worktree: bool = Field(default=False, description="Whether workspace is a git worktree")
    base_commit: Optional[str] = Field(default=None, description="Git commit hash workspace was created from")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Workspace creation timestamp")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")


class WorkspaceManager:
    """
    Manages task workspaces in /home/hackdac/Desktop/intern/LLMorch/workspaces/<workflow_id>/<task_id>.
    Uses git worktree when repository is a git repository, or directory clone as fallback.
    """

    def __init__(self, base_workspaces_dir: Optional[str] = None):
        if base_workspaces_dir:
            self.base_dir = Path(base_workspaces_dir)
        else:
            self.base_dir = Path(__file__).resolve().parent.parent / "workspaces"

        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_workspace(self, repo_root: str, workflow_id: str, task_id: str, git_commit: Optional[str] = None) -> Workspace:
        target_dir = self.base_dir / workflow_id / task_id
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        target_dir.mkdir(parents=True, exist_ok=True)

        repo_path = Path(repo_root)
        is_worktree = False

        if (repo_path / ".git").exists():
            # Attempt git worktree add
            try:
                cmd = ["git", "worktree", "add", "--detach", str(target_dir)]
                if git_commit:
                    cmd.append(git_commit)
                subprocess.run(cmd, cwd=str(repo_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                is_worktree = True
            except Exception:
                # Fallback to file copy if worktree fails
                is_worktree = False

        if not is_worktree:
            # Fallback: create symlink or lightweight directory structure
            # For safe non-destructive read, link or copy necessary files
            for item in repo_path.iterdir():
                if item.name in {".git", "workspaces", "history", ".venv", "node_modules"}:
                    continue
                dest = target_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, symlinks=True, ignore=shutil.ignore_patterns(".git"))
                else:
                    shutil.copy2(item, dest)

        return Workspace(
            workflow_id=workflow_id,
            task_id=task_id,
            working_directory=str(target_dir.resolve()),
            is_git_worktree=is_worktree,
            base_commit=git_commit
        )

    def cleanup_workspace(self, workspace: Workspace):
        target_dir = Path(workspace.working_directory)
        if not target_dir.exists():
            return

        if workspace.is_git_worktree:
            try:
                repo_root = target_dir.parent.parent.parent # Or original repo
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(target_dir)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            except Exception:
                shutil.rmtree(target_dir, ignore_errors=True)
        else:
            shutil.rmtree(target_dir, ignore_errors=True)
