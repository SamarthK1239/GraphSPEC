"""Scaffolds the GraphSPEC spec-driven workflow into a target repo (`graph-mcp init`)."""

from __future__ import annotations

from importlib.resources import as_file, files
from importlib.resources.abc import Traversable
from pathlib import Path

_GITIGNORE_SNIPPET_NAME = "gitignore-snippet.txt"
_CONFIG_TEMPLATE_NAME = "graph-mcp.toml.tmpl"


def _iter_files(base: Traversable, prefix: str = "") -> list[tuple[str, Traversable]]:
    entries: list[tuple[str, Traversable]] = []
    for entry in sorted(base.iterdir(), key=lambda e: e.name):
        rel = f"{prefix}{entry.name}"
        if entry.is_dir():
            entries.extend(_iter_files(entry, f"{rel}/"))
        else:
            entries.append((rel, entry))
    return entries


def _append_gitignore(target: Path, snippet: str) -> str:
    gitignore = target / ".gitignore"
    existing = gitignore.read_text() if gitignore.exists() else ""
    new_lines = [line for line in snippet.splitlines() if line and line not in existing.splitlines()]
    if not new_lines:
        return "unchanged"
    with gitignore.open("a") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write("\n".join(new_lines) + "\n")
    return "created" if not existing else "appended"


def scaffold_project(target: Path, *, force: bool = False) -> list[tuple[str, str]]:
    """Copy the bundled scaffold tree into `target`; returns [(relative_path, status)].

    Existing files are left untouched unless `force` is set. `gitignore-snippet.txt`
    is appended into `target/.gitignore` instead of overwriting it, and
    `graph-mcp.toml.tmpl` is written out as `.graph-mcp.toml`.
    """
    target = target.resolve()
    scaffold_root = files("graph_mcp") / "scaffold"
    report: list[tuple[str, str]] = []

    with as_file(scaffold_root) as scaffold_dir:
        for rel_path, resource in _iter_files(scaffold_dir):
            if rel_path == _GITIGNORE_SNIPPET_NAME:
                report.append((".gitignore", _append_gitignore(target, resource.read_text())))
                continue

            dest_rel = ".graph-mcp.toml" if rel_path == _CONFIG_TEMPLATE_NAME else rel_path
            dest = target / dest_rel
            if dest.exists() and not force:
                report.append((dest_rel, "skipped"))
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(resource.read_bytes())
            report.append((dest_rel, "created"))

    return report
