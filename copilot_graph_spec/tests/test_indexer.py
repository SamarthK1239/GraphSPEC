"""Tests for the Phase 1 indexer: extraction and end-to-end SQLite indexing."""

from __future__ import annotations

from pathlib import Path

from copilot_graph_spec.indexer.core import build_index
from copilot_graph_spec.indexer.extractor import extract_file


def test_extract_python_functions_and_calls() -> None:
    source = b"def helper():\n    return 1\n\n\ndef main():\n    return helper()\n"
    nodes, edges = extract_file("mod.py", source, "python")

    symbol_names = {n.name for n in nodes if n.type == "symbol"}
    assert symbol_names == {"helper", "main"}

    calls = [(e.src, e.dst) for e in edges if e.type == "calls"]
    helper_id = next(n.id for n in nodes if n.name == "helper")
    main_id = next(n.id for n in nodes if n.name == "main")
    assert (main_id, helper_id) in calls


def test_extract_python_class_and_self_call() -> None:
    source = b"class A:\n    def bar(self):\n        return self.baz()\n\n    def baz(self):\n        return 1\n"
    nodes, edges = extract_file("mod.py", source, "python")

    class_node = next(n for n in nodes if n.name == "A")
    assert class_node.meta.find('"kind": "class"') != -1

    bar_id = next(n.id for n in nodes if n.name == "A.bar")
    baz_id = next(n.id for n in nodes if n.name == "A.baz")
    calls = [(e.src, e.dst) for e in edges if e.type == "calls"]
    assert (bar_id, baz_id) in calls


def test_attribute_call_on_unrelated_object_is_not_resolved() -> None:
    # `sqlite3.connect()` must not resolve against a same-named local `connect`.
    source = b"import sqlite3\n\n\ndef connect():\n    return sqlite3.connect('x')\n"
    nodes, edges = extract_file("mod.py", source, "python")

    connect_id = next(n.id for n in nodes if n.name == "connect")
    calls = [(e.src, e.dst) for e in edges if e.type == "calls"]
    assert (connect_id, connect_id) not in calls


def test_contains_and_imports_edges() -> None:
    source = b"import os\nfrom foo.bar import baz\n\n\ndef f():\n    pass\n"
    nodes, edges = extract_file("mod.py", source, "python")

    file_id = "file:mod.py"
    f_id = next(n.id for n in nodes if n.name == "f")
    contains = [(e.src, e.dst) for e in edges if e.type == "contains"]
    assert (file_id, f_id) in contains

    imports = {e.dst for e in edges if e.type == "imports"}
    assert "external:os" in imports
    assert "external:foo.bar" in imports


def test_build_index_writes_nodes_edges_and_fts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def foo():\n    return 1\n")
    db_path = tmp_path / ".graph" / "graph.db"

    stats = build_index(repo, db_path)

    assert stats.files_indexed == 1
    assert stats.nodes >= 2  # file + symbol
    assert db_path.exists()

    import sqlite3

    conn = sqlite3.connect(db_path)
    node_count = conn.execute("SELECT count(*) FROM nodes").fetchone()[0]
    fts_count = conn.execute("SELECT count(*) FROM nodes_fts").fetchone()[0]
    assert node_count == stats.nodes
    assert fts_count == stats.nodes
    match = conn.execute("SELECT node_id FROM nodes_fts WHERE nodes_fts MATCH 'foo'").fetchall()
    assert match
