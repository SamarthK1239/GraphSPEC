"""Filesystem walk yielding (absolute_path, repo_relative_path) for indexable files."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from graph_mcp.indexer.languages import detect_language

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".graph",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".egg-info",
}


def walk_repo(root: str | Path) -> Iterator[tuple[Path, str]]:
    root = Path(root).resolve()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS or part.endswith(".egg-info") for part in path.relative_to(root).parts[:-1]):
            continue
        if detect_language(path.name) is None:
            continue
        yield path, path.relative_to(root).as_posix()
