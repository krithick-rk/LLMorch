"""
LLMorch Noise Filter Module
Deterministic classification of repository paths to optimize LLM context size.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple


class FileClassification(str, Enum):
    ANALYZE = "ANALYZE"
    LOW_PRIORITY = "LOW_PRIORITY"
    IGNORE_FOR_LLM_CONTEXT = "IGNORE_FOR_LLM_CONTEXT"
    GENERATED = "GENERATED"
    VENDOR = "VENDOR"
    BUILD_ARTIFACT = "BUILD_ARTIFACT"
    NOISE = "NOISE"


class NoiseFilter:
    """
    Classifies repository files into relevance buckets to prevent sending
    build artifacts, cache files, binary assets, and noise to LLMs.
    """

    IGNORE_DIRS = {
        ".git", ".svn", ".hg", "node_modules", "__pycache__", ".pytest_cache",
        "build", "dist", "out", "target", ".bazel-out", "bazel-out", ".cargo",
        ".venv", "venv", "env", ".idea", ".vscode"
    }

    IGNORE_EXTENSIONS = {
        ".pyc", ".pyo", ".pyd", ".o", ".obj", ".a", ".lib", ".so", ".dylib",
        ".dll", ".exe", ".bin", ".tar", ".gz", ".zip", ".7z", ".png", ".jpg",
        ".jpeg", ".gif", ".ico", ".pdf", ".vcd", ".fst", ".swp", ".swo"
    }

    LOW_PRIORITY_DIRS = {"docs", "doc", "examples", "tests", "test", "third_party", "vendor"}

    @classmethod
    def classify_path(cls, file_path: str, repo_root: str = "") -> FileClassification:
        rel_path = file_path
        if repo_root and file_path.startswith(repo_root):
            rel_path = os.path.relpath(file_path, repo_root)

        path_obj = Path(rel_path)
        parts = path_obj.parts

        # Check ignored directories
        for part in parts:
            if part in cls.IGNORE_DIRS:
                return FileClassification.IGNORE_FOR_LLM_CONTEXT

        # Check ignored extensions
        if path_obj.suffix.lower() in cls.IGNORE_EXTENSIONS:
            return FileClassification.IGNORE_FOR_LLM_CONTEXT

        # Check low priority directories
        for part in parts[:-1]:
            if part.lower() in cls.LOW_PRIORITY_DIRS:
                if part.lower() in {"third_party", "vendor"}:
                    return FileClassification.VENDOR
                return FileClassification.LOW_PRIORITY

        return FileClassification.ANALYZE

    @classmethod
    def filter_paths_for_llm(cls, file_paths: List[str], repo_root: str = "") -> List[str]:
        """Returns list of paths classified as ANALYZE or LOW_PRIORITY."""
        return [
            p for p in file_paths
            if cls.classify_path(p, repo_root) in (FileClassification.ANALYZE, FileClassification.LOW_PRIORITY)
        ]
