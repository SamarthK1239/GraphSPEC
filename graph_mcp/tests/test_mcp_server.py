"""Tests for Phase 2: db_queries, read_span, and the MCP server tool wiring."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from graph_mcp.db import connect
from graph_mcp.mcp_server import db_queries
from graph_mcp.mcp_server.read_span import read_span
from graph_mcp.mcp_server.server import build_server


def _insert_node(conn: sqlite3.Connection, **kwargs) -> None:
    defaults = {
        "id": None,
        "type": "symbol",
        "path": None,
        "name": None,
        "signature": None,
        "line_start": None,
        "line_end": None,
        "hash": None,
        "meta": "{}",
    }
    defaults.update(kwargs)
    conn.execute(
        "INSERT INTO nodes (id, type, path, name, signature, line_start, line_end, hash, meta) "
        "VALUES (:id, :type, :path, :name, :signature, :line_start, :line_end, :hash, :meta)",
        defaults,
    )
    conn.execute(
        "INSERT INTO nodes_fts (node_id, name, signature, doc) VALUES (?, ?, ?, ?)",
        (defaults["id"], defaults["name"], defaults["signature"], None),
    )


def _insert_edge(conn: sqlite3.Connection, src: str, dst: str, edge_type: str) -> None:
    conn.execute("INSERT INTO edges (src, dst, type) VALUES (?, ?, ?)", (src, dst, edge_type))


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "graph.db"
    conn = connect(path)

    _insert_node(conn, id="file:a.py", type="file", path="a.py", name="a.py", line_start=1, line_end=10)
    _insert_node(conn, id="symbol:a.py:foo:1", path="a.py", name="foo", signature="def foo()", line_start=1, line_end=2)
    _insert_node(conn, id="symbol:a.py:bar:4", path="a.py", name="bar", signature="def bar()", line_start=4, line_end=6)
    _insert_edge(conn, "file:a.py", "symbol:a.py:foo:1", "contains")
    _insert_edge(conn, "file:a.py", "symbol:a.py:bar:4", "contains")
    _insert_edge(conn, "symbol:a.py:bar:4", "symbol:a.py:foo:1", "calls")

    _insert_node(conn, id="requirement:covered", type="requirement", name="Covered requirement", meta=json.dumps({}))
    _insert_node(conn, id="requirement:gap", type="requirement", name="Uncovered requirement", meta=json.dumps({}))
    _insert_node(conn, id="task:t1", type="task", name="Task 1", meta=json.dumps({}))
    _insert_edge(conn, "task:t1", "requirement:covered", "covers")

    conn.commit()
    conn.close()
    return path


def test_search_finds_by_name(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    results = db_queries.search(conn, "foo")
    assert any(r["id"] == "symbol:a.py:foo:1" for r in results)


def test_search_tolerates_special_characters(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Would raise an FTS5 syntax error if passed through unescaped.
    results = db_queries.search(conn, 'foo"bar: OR NOT')
    assert results == []


def test_file_outline_orders_by_line(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    outline = db_queries.file_outline(conn, "a.py")
    assert [n["name"] for n in outline] == ["foo", "bar"]


def test_get_symbol_missing_returns_none(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    assert db_queries.get_symbol(conn, "nope") is None


def test_neighbors_direction_filtering(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    result = db_queries.neighbors(conn, "symbol:a.py:bar:4", direction="out", edge_types=["calls"])
    assert result["incoming"] == []
    assert [n["id"] for n in result["outgoing"]] == ["symbol:a.py:foo:1"]


def test_impact_bfs(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    impacted = db_queries.impact(conn, "symbol:a.py:foo:1", max_depth=2)
    assert any(n["id"] == "symbol:a.py:bar:4" and n["depth"] == 1 for n in impacted)


def test_subgraph_respects_max_nodes(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    result = db_queries.subgraph(conn, ["file:a.py"], max_nodes=2, max_depth=3)
    assert len(result["nodes"]) <= 2


def test_trace_reports_coverage_gap(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    result = db_queries.trace(conn)
    gap_ids = {n["id"] for n in result["coverage_gaps"]}
    assert "requirement:gap" in gap_ids
    assert "requirement:covered" not in gap_ids


def test_trace_with_node_id_returns_neighbors(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    result = db_queries.trace(conn, "task:t1")
    assert [n["id"] for n in result["outgoing"]] == ["requirement:covered"]


def test_read_span_happy_path(tmp_path: Path) -> None:
    (tmp_path / "f.py").write_text("line1\nline2\nline3\n")
    assert read_span(tmp_path, "f.py", 2, 3) == "line2\nline3"


def test_read_span_rejects_path_traversal(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "secret.txt").write_text("nope")
    with pytest.raises(ValueError):
        read_span(repo, "../secret.txt", 1, 1)


def test_read_span_rejects_oversized_span(tmp_path: Path) -> None:
    content = "\n".join(str(i) for i in range(1000))
    (tmp_path / "big.py").write_text(content)
    with pytest.raises(ValueError):
        read_span(tmp_path, "big.py", 1, 999)


def test_mcp_server_graph_search_tool(db_path: Path, tmp_path: Path) -> None:
    server = build_server(db_path, tmp_path)

    async def run():
        return await server.call_tool("graph_search", {"query": "foo"})

    result = asyncio.run(run())
    assert result.is_error is False
    payload = json.loads(result.content[0].text)
    assert any(r["id"] == "symbol:a.py:foo:1" for r in payload["results"])


def test_mcp_server_graph_read_span_tool(db_path: Path, tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def foo():\n    return 1\n")
    server = build_server(db_path, tmp_path)

    async def run():
        return await server.call_tool("graph_read_span", {"path": "a.py", "line_start": 1, "line_end": 2})

    result = asyncio.run(run())
    payload = json.loads(result.content[0].text)
    assert payload["text"] == "def foo():\n    return 1"


def test_mcp_server_lists_all_eight_tools(db_path: Path, tmp_path: Path) -> None:
    server = build_server(db_path, tmp_path)

    async def run():
        return await server.list_tools()

    tools = {t.name for t in asyncio.run(run())}
    assert tools == {
        "graph_search",
        "graph_file_outline",
        "graph_get_symbol",
        "graph_neighbors",
        "graph_impact",
        "graph_subgraph",
        "graph_read_span",
        "graph_trace",
    }
