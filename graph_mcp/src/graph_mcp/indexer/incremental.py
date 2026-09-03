"""Incremental re-index: only re-parse files whose content actually changed.

Uses mtime as a fast pre-check and content hash as the authoritative check
(so touching a file without changing it doesn't trigger a re-parse). Removed
files have their nodes/edges/embeddings purged. The spec/plan/tasks graph is
cheap to parse and is always fully refreshed rather than tracked per-file.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from graph_mcp.db import connect
from graph_mcp.indexer.core import IndexStats, write_records
from graph_mcp.indexer.extractor import extract_file
from graph_mcp.indexer.languages import detect_language
from graph_mcp.indexer.spec_parser import extract_spec_features
from graph_mcp.indexer.walker import walk_repo


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _purge_ids(conn: sqlite3.Connection, ids: list[str]) -> None:
    if not ids:
        return
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"DELETE FROM nodes_fts WHERE node_id IN ({placeholders})", ids)
    conn.execute(f"DELETE FROM edges WHERE src IN ({placeholders}) OR dst IN ({placeholders})", [*ids, *ids])
    conn.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", ids)
    if conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'vec_nodes'").fetchone():
        conn.execute(f"DELETE FROM vec_nodes WHERE node_id IN ({placeholders})", ids)


def _purge_path(conn: sqlite3.Connection, path: str) -> None:
    ids = [r["id"] for r in conn.execute("SELECT id FROM nodes WHERE path = ?", (path,)).fetchall()]
    _purge_ids(conn, ids)


def incremental_index(root: str | Path, db_path: str | Path) -> IndexStats:
    stats = IndexStats()
    root = Path(root)
    conn = connect(db_path)

    known = {
        r["path"]: (r["mtime"], r["hash"]) for r in conn.execute("SELECT path, mtime, hash FROM indexed_files").fetchall()
    }
    seen_paths: set[str] = set()

    for abs_path, relpath in walk_repo(root):
        language_key = detect_language(relpath)
        if language_key is None:
            continue
        seen_paths.add(relpath)

        mtime = abs_path.stat().st_mtime
        prev = known.get(relpath)
        if prev is not None and prev[0] == mtime:
            continue  # fast path: mtime unchanged, assume content unchanged

        try:
            source = abs_path.read_bytes()
        except OSError:
            stats.files_skipped += 1
            continue
        content_hash = _hash_bytes(source)
        if prev is not None and prev[1] == content_hash:
            conn.execute("UPDATE indexed_files SET mtime = ? WHERE path = ?", (mtime, relpath))
            continue  # touched but content identical (e.g. checkout, chmod)

        _purge_path(conn, relpath)
        try:
            file_nodes, file_edges = extract_file(relpath, source, language_key)
        except (UnicodeDecodeError, ValueError):
            stats.files_skipped += 1
            conn.execute("DELETE FROM indexed_files WHERE path = ?", (relpath,))
            continue

        write_records(conn, file_nodes, file_edges)
        conn.execute(
            "INSERT OR REPLACE INTO indexed_files (path, mtime, hash) VALUES (?, ?, ?)",
            (relpath, mtime, content_hash),
        )
        stats.files_indexed += 1
        stats.nodes += len(file_nodes)
        stats.edges += len(file_edges)

    for relpath in set(known) - seen_paths:
        _purge_path(conn, relpath)
        conn.execute("DELETE FROM indexed_files WHERE path = ?", (relpath,))
        stats.files_removed += 1

    spec_ids = [
        r["id"]
        for r in conn.execute("SELECT id FROM nodes WHERE type IN ('spec', 'requirement', 'plan_item', 'task')").fetchall()
    ]
    _purge_ids(conn, spec_ids)
    spec_nodes, spec_edges = extract_spec_features(root / "spec")
    write_records(conn, spec_nodes, spec_edges)
    stats.nodes += len(spec_nodes)
    stats.edges += len(spec_edges)

    conn.commit()
    conn.close()
    return stats
