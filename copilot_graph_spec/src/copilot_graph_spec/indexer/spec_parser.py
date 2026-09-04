"""Parses spec/features/<slug>/{spec.md,plan.md,tasks.md} into spec/requirement/
plan_item/task nodes and contains/derives/covers/implements edges, per the
REQ-<NNN>/PLAN-<NNN>/TASK-<NNN> convention documented in spec/constitution.md.

Bullets may wrap across multiple physical lines (indented continuation
lines, as real Markdown authoring commonly does); continuation lines are
joined onto the bullet's first line before applying the per-kind regex, so
tags like `[derives: ...]` are found regardless of which physical line they
land on.

Runs independently of the tree-sitter code indexer (different node types,
different source format) but writes into the same nodes/edges tables.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from graph_mcp.indexer.models import EdgeRecord, NodeRecord

_REQ_START_RE = re.compile(r"^-\s*REQ-\d+:")
_PLAN_START_RE = re.compile(r"^-\s*PLAN-\d+:")
_TASK_START_RE = re.compile(r"^-\s*\[[ xX]\]\s*TASK-\d+:")

_REQ_RE = re.compile(r"^-\s*REQ-(\d+):\s*(.+?)\s*$")
_PLAN_RE = re.compile(r"^-\s*PLAN-(\d+):\s*(.+?)(?:\s*\[derives:\s*([^\]]+)\])?\s*$")
_TASK_RE = re.compile(
    r"^-\s*\[([ xX])\]\s*TASK-(\d+):\s*(.+?)(?:\s*\[covers:\s*([^\]]+)\])?(?:\s*\[implements:\s*([^\]]+)\])?\s*$"
)


def _split_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [tok.strip() for tok in raw.split(",") if tok.strip()]


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _collect_entries(text: str, start_re: re.Pattern[str]) -> list[tuple[int, int, str]]:
    """Find bullets matching start_re and join any indented continuation
    lines that follow, returning (line_start, line_end, joined_text)."""
    lines = text.splitlines()
    entries: list[tuple[int, int, str]] = []
    i = 0
    n = len(lines)
    while i < n:
        stripped = lines[i].strip()
        if not start_re.match(stripped):
            i += 1
            continue
        parts = [stripped]
        j = i + 1
        while j < n and lines[j].strip() and (lines[j][0] in " \t") and not lines[j].lstrip().startswith("-"):
            parts.append(lines[j].strip())
            j += 1
        entries.append((i + 1, j, " ".join(parts)))
        i = j
    return entries


def extract_spec_features(spec_root: Path) -> tuple[list[NodeRecord], list[EdgeRecord]]:
    """spec_root is the `spec/` directory; paths are recorded relative to its parent (repo root)."""
    nodes: list[NodeRecord] = []
    edges: list[EdgeRecord] = []
    features_dir = spec_root / "features"
    if not features_dir.is_dir():
        return nodes, edges

    repo_root = spec_root.parent
    for feature_dir in sorted(p for p in features_dir.iterdir() if p.is_dir()):
        slug = feature_dir.name
        spec_path = feature_dir / "spec.md"
        plan_path = feature_dir / "plan.md"
        tasks_path = feature_dir / "tasks.md"

        if spec_path.is_file():
            text = spec_path.read_text(encoding="utf-8", errors="replace")
            rel = spec_path.relative_to(repo_root).as_posix()
            spec_id = f"spec:{slug}"
            nodes.append(
                NodeRecord(
                    id=spec_id,
                    type="spec",
                    path=rel,
                    name=slug,
                    signature=None,
                    line_start=1,
                    line_end=len(text.splitlines()) or 1,
                    hash=_hash(text),
                    meta=json.dumps({"slug": slug}),
                )
            )
            for line_start, line_end, joined in _collect_entries(text, _REQ_START_RE):
                m = _REQ_RE.match(joined)
                if not m:
                    continue
                num, desc = m.groups()
                req_id = f"requirement:{slug}:REQ-{num}"
                nodes.append(
                    NodeRecord(
                        id=req_id,
                        type="requirement",
                        path=rel,
                        name=f"REQ-{num}",
                        signature=desc,
                        line_start=line_start,
                        line_end=line_end,
                        hash=_hash(joined),
                        meta=json.dumps({"slug": slug}),
                    )
                )
                edges.append(EdgeRecord(spec_id, req_id, "contains"))

        if plan_path.is_file():
            text = plan_path.read_text(encoding="utf-8", errors="replace")
            rel = plan_path.relative_to(repo_root).as_posix()
            for line_start, line_end, joined in _collect_entries(text, _PLAN_START_RE):
                m = _PLAN_RE.match(joined)
                if not m:
                    continue
                num, desc, derives_raw = m.groups()
                plan_id = f"plan_item:{slug}:PLAN-{num}"
                nodes.append(
                    NodeRecord(
                        id=plan_id,
                        type="plan_item",
                        path=rel,
                        name=f"PLAN-{num}",
                        signature=desc,
                        line_start=line_start,
                        line_end=line_end,
                        hash=_hash(joined),
                        meta=json.dumps({"slug": slug}),
                    )
                )
                for req_ref in _split_ids(derives_raw):
                    edges.append(EdgeRecord(plan_id, f"requirement:{slug}:{req_ref}", "derives"))

        if tasks_path.is_file():
            text = tasks_path.read_text(encoding="utf-8", errors="replace")
            rel = tasks_path.relative_to(repo_root).as_posix()
            for line_start, line_end, joined in _collect_entries(text, _TASK_START_RE):
                m = _TASK_RE.match(joined)
                if not m:
                    continue
                checked, num, desc, covers_raw, implements_raw = m.groups()
                task_id = f"task:{slug}:TASK-{num}"
                nodes.append(
                    NodeRecord(
                        id=task_id,
                        type="task",
                        path=rel,
                        name=f"TASK-{num}",
                        signature=desc,
                        line_start=line_start,
                        line_end=line_end,
                        hash=_hash(joined),
                        meta=json.dumps({"slug": slug, "done": checked.lower() == "x"}),
                    )
                )
                for req_ref in _split_ids(covers_raw):
                    edges.append(EdgeRecord(task_id, f"requirement:{slug}:{req_ref}", "covers"))
                for plan_ref in _split_ids(implements_raw):
                    edges.append(EdgeRecord(task_id, f"plan_item:{slug}:{plan_ref}", "implements"))

    return nodes, edges

