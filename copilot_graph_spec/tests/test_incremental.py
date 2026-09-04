"""Tests for Phase 7: incremental indexing (skip-unchanged, re-parse-changed,
purge-removed) and re-embed-only-missing behavior.
"""

from __future__ import annotations

import time
from pathlib import Path

from copilot_graph_spec.db import connect
from copilot_graph_spec.embeddings.indexer import embed_nodes
from copilot_graph_spec.indexer.core import build_index
from copilot_graph_spec.indexer.incremental import incremental_index
from copilot_graph_spec.mcp_server import db_queries


class StubEmbedder:
    dimension = 3

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


def test_incremental_index_skips_unchanged_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def foo():\n    return 1\n")
    db_path = tmp_path / "graph.db"

    first = build_index(repo, db_path)
    assert first.files_indexed == 1

    second = incremental_index(repo, db_path)
    assert second.files_indexed == 0
    assert second.files_removed == 0


def test_incremental_index_reparses_changed_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    a_py = repo / "a.py"
    a_py.write_text("def foo():\n    return 1\n")
    db_path = tmp_path / "graph.db"
    build_index(repo, db_path)

    time.sleep(0.01)
    a_py.write_text("def foo():\n    return 1\n\n\ndef bar():\n    return 2\n")
    stats = incremental_index(repo, db_path)
    assert stats.files_indexed == 1

    conn = connect(db_path)
    names = {r["name"] for r in conn.execute("SELECT name FROM nodes WHERE type = 'symbol'").fetchall()}
    assert names == {"foo", "bar"}


def test_incremental_index_touch_without_change_is_a_noop(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    a_py = repo / "a.py"
    a_py.write_text("def foo():\n    return 1\n")
    db_path = tmp_path / "graph.db"
    build_index(repo, db_path)

    time.sleep(0.01)
    a_py.write_text("def foo():\n    return 1\n")  # same content, new mtime
    stats = incremental_index(repo, db_path)
    assert stats.files_indexed == 0  # content hash matched, so no re-parse


def test_incremental_index_purges_removed_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    a_py = repo / "a.py"
    a_py.write_text("def foo():\n    return 1\n")
    db_path = tmp_path / "graph.db"
    build_index(repo, db_path)

    a_py.unlink()
    stats = incremental_index(repo, db_path)
    assert stats.files_removed == 1

    conn = connect(db_path)
    remaining = conn.execute("SELECT count(*) FROM nodes WHERE path = 'a.py'").fetchone()[0]
    assert remaining == 0


def test_incremental_index_purges_vec_nodes_for_changed_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    a_py = repo / "a.py"
    a_py.write_text("def foo():\n    return 1\n")
    db_path = tmp_path / "graph.db"
    build_index(repo, db_path)

    conn = connect(db_path)
    embed_nodes(conn, StubEmbedder(), only_missing=False)
    before = conn.execute("SELECT count(*) FROM vec_nodes").fetchone()[0]
    assert before > 0
    conn.close()

    time.sleep(0.01)
    a_py.write_text("def foo():\n    return 2\n")
    incremental_index(repo, db_path)

    conn = connect(db_path)
    # The old foo's vec row was purged; embed_nodes(only_missing=True) should
    # need to recompute it (i.e. it's no longer present after the purge).
    assert db_queries.vec_table_exists(conn)
    remaining = conn.execute(
        "SELECT count(*) FROM vec_nodes WHERE node_id IN (SELECT id FROM nodes WHERE path = 'a.py')"
    ).fetchone()[0]
    assert remaining == 0


def test_embed_nodes_only_missing_skips_already_embedded(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def foo():\n    return 1\n")
    (repo / "b.py").write_text("def bar():\n    return 2\n")
    db_path = tmp_path / "graph.db"
    build_index(repo, db_path)

    conn = connect(db_path)
    first_count = embed_nodes(conn, StubEmbedder(), only_missing=True)
    assert first_count > 0

    second_count = embed_nodes(conn, StubEmbedder(), only_missing=True)
    assert second_count == 0  # everything already has a vec_nodes row

    third_count = embed_nodes(conn, StubEmbedder(), only_missing=False)
    assert third_count == first_count  # --force recomputes everything
