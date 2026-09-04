"""Tests for Phase 6: parsing spec/features/** into spec/requirement/plan_item/task
nodes and contains/derives/covers/implements edges, and end-to-end coverage-gap
detection via db_queries.trace() using real parsed data (not synthetic rows).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from copilot_graph_spec.db import connect
from copilot_graph_spec.indexer.core import build_index
from copilot_graph_spec.indexer.spec_parser import extract_spec_features
from copilot_graph_spec.mcp_server import db_queries


def _write_feature(spec_root: Path, slug: str, spec_md: str, plan_md: str, tasks_md: str) -> None:
    feature_dir = spec_root / "features" / slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(spec_md)
    (feature_dir / "plan.md").write_text(plan_md)
    (feature_dir / "tasks.md").write_text(tasks_md)


def test_extract_spec_features_parses_reqs_plans_tasks(tmp_path: Path) -> None:
    spec_root = tmp_path / "spec"
    _write_feature(
        spec_root,
        "widgets",
        spec_md="# Widgets\n\n## Requirements\n\n- REQ-001: Users can create a widget.\n- REQ-002: Users can delete a widget.\n",
        plan_md="# Plan\n\n## Plan Items\n\n- PLAN-001: Add widget model. [derives: REQ-001]\n",
        tasks_md="# Tasks\n\n- [x] TASK-001: Implement widget model. [covers: REQ-001] [implements: PLAN-001]\n"
        "- [ ] TASK-002: Implement widget deletion. [covers: REQ-002]\n",
    )

    nodes, edges = extract_spec_features(spec_root)

    node_ids = {n.id for n in nodes}
    assert "spec:widgets" in node_ids
    assert "requirement:widgets:REQ-001" in node_ids
    assert "requirement:widgets:REQ-002" in node_ids
    assert "plan_item:widgets:PLAN-001" in node_ids
    assert "task:widgets:TASK-001" in node_ids
    assert "task:widgets:TASK-002" in node_ids

    edge_tuples = {(e.src, e.dst, e.type) for e in edges}
    assert ("spec:widgets", "requirement:widgets:REQ-001", "contains") in edge_tuples
    assert ("plan_item:widgets:PLAN-001", "requirement:widgets:REQ-001", "derives") in edge_tuples
    assert ("task:widgets:TASK-001", "requirement:widgets:REQ-001", "covers") in edge_tuples
    assert ("task:widgets:TASK-001", "plan_item:widgets:PLAN-001", "implements") in edge_tuples
    assert ("task:widgets:TASK-002", "requirement:widgets:REQ-002", "covers") in edge_tuples

    task1 = next(n for n in nodes if n.id == "task:widgets:TASK-001")
    task2 = next(n for n in nodes if n.id == "task:widgets:TASK-002")
    assert '"done": true' in task1.meta
    assert '"done": false' in task2.meta


def test_extract_spec_features_missing_features_dir_returns_empty(tmp_path: Path) -> None:
    nodes, edges = extract_spec_features(tmp_path / "spec")
    assert nodes == []
    assert edges == []


def test_extract_spec_features_joins_wrapped_multiline_bullets(tmp_path: Path) -> None:
    # Regression test: a real subagent-authored plan.md wrapped a PLAN item's
    # description across three lines, with the [derives: ...] tag on the
    # *last* line -- the parser must join continuation lines before matching,
    # not just look at the bullet's first physical line.
    spec_root = tmp_path / "spec"
    _write_feature(
        spec_root,
        "wrapped",
        spec_md="- REQ-001: A requirement whose description wraps onto a\n  second physical line for readability.\n",
        plan_md=(
            "- PLAN-001: Add a long decorator to the CLI so the flag works\n"
            "  without requiring a subcommand, printing the installed\n"
            "  version. [derives: REQ-001]\n"
        ),
        tasks_md="- [x] TASK-001: Do the thing.\n  Some more detail. [covers: REQ-001] [implements: PLAN-001]\n",
    )

    nodes, edges = extract_spec_features(spec_root)
    edge_tuples = {(e.src, e.dst, e.type) for e in edges}

    assert ("plan_item:wrapped:PLAN-001", "requirement:wrapped:REQ-001", "derives") in edge_tuples
    assert ("task:wrapped:TASK-001", "requirement:wrapped:REQ-001", "covers") in edge_tuples
    assert ("task:wrapped:TASK-001", "plan_item:wrapped:PLAN-001", "implements") in edge_tuples

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE nodes (id TEXT PRIMARY KEY, type TEXT, path TEXT, name TEXT, signature TEXT, "
        "line_start INT, line_end INT, hash TEXT, meta TEXT); "
        "CREATE TABLE edges (src TEXT, dst TEXT, type TEXT);"
    )
    for n in nodes:
        conn.execute(
            "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (n.id, n.type, n.path, n.name, n.signature, n.line_start, n.line_end, n.hash, n.meta),
        )
    for e in edges:
        conn.execute("INSERT INTO edges VALUES (?, ?, ?)", (e.src, e.dst, e.type))
    result = db_queries.trace(conn)
    assert result["coverage_gaps"] == []  # REQ-001 is covered despite the wrapped [derives: ...] tag


def test_build_index_includes_spec_features_and_trace_finds_real_gap(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_feature(
        repo / "spec",
        "widgets",
        spec_md="- REQ-001: Covered requirement.\n- REQ-002: Uncovered requirement.\n",
        plan_md="- PLAN-001: Plan for REQ-001. [derives: REQ-001]\n",
        tasks_md="- [x] TASK-001: Implements PLAN-001. [covers: REQ-001] [implements: PLAN-001]\n",
    )

    stats = build_index(repo, tmp_path / "graph.db")
    assert stats.nodes >= 5  # spec + 2 requirements + 1 plan_item + 1 task (+ any code files)

    conn = connect(tmp_path / "graph.db")
    conn.row_factory = sqlite3.Row

    result = db_queries.trace(conn)
    gap_ids = {n["id"] for n in result["coverage_gaps"]}
    assert "requirement:widgets:REQ-002" in gap_ids
    assert "requirement:widgets:REQ-001" not in gap_ids
    # Tasks are always the *source* of covers/implements edges, never the
    # target, so they must never be flagged as coverage gaps themselves.
    assert "task:widgets:TASK-001" not in gap_ids

    searched = db_queries.search(conn, "Uncovered")
    assert any(n["id"] == "requirement:widgets:REQ-002" for n in searched)
