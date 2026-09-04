"""Tests for Phase 3: pluggable embedder wiring, vec_nodes storage, and hybrid search.

Uses a deterministic in-repo StubEmbedder rather than the real fastembed model,
so these tests stay fast/offline. The real fastembed backend was verified
manually (model download + embedding shape) since exercising it in the
automated suite would require a network-dependent model download on first run.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec

from copilot_graph_spec.db import connect
from copilot_graph_spec.embeddings.indexer import embed_nodes, ensure_vec_table
from copilot_graph_spec.mcp_server import db_queries


class StubEmbedder:
    def __init__(self, mapping: dict[str, list[float]], dimension: int = 3) -> None:
        self.dimension = dimension
        self._mapping = mapping

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._mapping.get(t, [0.0] * self.dimension) for t in texts]


def _insert_node(conn: sqlite3.Connection, node_id: str, name: str, signature: str) -> None:
    conn.execute(
        "INSERT INTO nodes (id, type, path, name, signature, line_start, line_end, hash, meta) "
        "VALUES (?, 'symbol', 'a.py', ?, ?, 1, 1, 'h', '{}')",
        (node_id, name, signature),
    )
    conn.execute("INSERT INTO nodes_fts (node_id, name, signature, doc) VALUES (?, ?, ?, NULL)", (node_id, name, signature))


def test_rrf_fuse_favors_ids_ranked_well_in_either_list() -> None:
    lexical = ["a", "b", "c"]
    vector = ["c", "d"]
    fused = db_queries._rrf_fuse(lexical, vector)
    # "c" ranks well in both lists, so it should come out on top.
    assert fused[0] == "c"
    assert set(fused) == {"a", "b", "c", "d"}


def test_hybrid_search_falls_back_to_lexical_without_embedder(tmp_path: Path) -> None:
    conn = connect(tmp_path / "graph.db")
    _insert_node(conn, "sym:greet", "greet", "def greet()")
    conn.commit()

    lexical_only = db_queries.search(conn, "greet")
    hybrid_no_embedder = db_queries.hybrid_search(conn, "greet", embedder=None)
    assert [n["id"] for n in hybrid_no_embedder] == [n["id"] for n in lexical_only]


def test_hybrid_search_finds_semantic_match_without_keyword_overlap(tmp_path: Path) -> None:
    conn = connect(tmp_path / "graph.db")
    _insert_node(conn, "sym:greet", "greet", "def greet()")
    _insert_node(conn, "sym:unrelated", "unrelated_func", "def unrelated_func()")
    conn.commit()

    ensure_vec_table(conn, dimension=3)
    conn.execute(
        "INSERT INTO vec_nodes (node_id, embedding) VALUES (?, ?)",
        ("sym:greet", sqlite_vec.serialize_float32([1.0, 0.0, 0.0])),
    )
    conn.execute(
        "INSERT INTO vec_nodes (node_id, embedding) VALUES (?, ?)",
        ("sym:unrelated", sqlite_vec.serialize_float32([0.0, 1.0, 0.0])),
    )
    conn.commit()

    query = "salutation phrase"  # shares no tokens with "greet"
    assert db_queries.search(conn, query) == []  # lexical alone finds nothing

    embedder = StubEmbedder({query: [0.9, 0.1, 0.0]})  # close to "greet"'s vector
    results = db_queries.hybrid_search(conn, query, embedder, limit=5)
    assert results[0]["id"] == "sym:greet"


def test_embed_nodes_populates_vec_table(tmp_path: Path) -> None:
    conn = connect(tmp_path / "graph.db")
    _insert_node(conn, "sym:a", "alpha", "def alpha()")
    _insert_node(conn, "sym:b", "beta", "def beta()")
    conn.commit()

    assert db_queries.vec_table_exists(conn) is False
    embedder = StubEmbedder({"alpha def alpha()": [1.0, 0.0, 0.0], "beta def beta()": [0.0, 1.0, 0.0]})
    count = embed_nodes(conn, embedder)

    assert count == 2
    assert db_queries.vec_table_exists(conn) is True
    row_count = conn.execute("SELECT count(*) FROM vec_nodes").fetchone()[0]
    assert row_count == 2
