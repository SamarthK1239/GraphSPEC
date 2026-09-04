"""Read an exact line span from disk, guarded against path traversal and oversized reads."""

from __future__ import annotations

from pathlib import Path

MAX_SPAN_LINES = 500


def read_span(repo_root: Path, path: str, line_start: int, line_end: int) -> str:
    root = repo_root.resolve()
    target = (root / path).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"path escapes repo root: {path}")
    if not target.is_file():
        raise FileNotFoundError(f"no such file: {path}")

    line_start = max(1, line_start)
    if line_end < line_start:
        raise ValueError("line_end must be >= line_start")
    if line_end - line_start + 1 > MAX_SPAN_LINES:
        raise ValueError(f"span too large: max {MAX_SPAN_LINES} lines")

    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[line_start - 1 : line_end])
