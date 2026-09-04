"""Orchestrates a full (re)index: walk repo -> parse -> extract -> write to SQLite."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from copilot_graph_spec.db import connect, reset
from copilot_graph_spec.indexer.extractor import extract_file
from copilot_graph_spec.indexer.languages import detect_language
from copilot_graph_spec.indexer.models import EdgeRecord, NodeRecord
from copilot_graph_spec.indexer.spec_parser import extract_spec_features
from copilot_graph_spec.indexer.walker import walk_repo


@dataclass
class IndexStats:
    files_indexed: int = 0
    files_skipped: int = 0
    files_removed: int = 0
    nodes: int = 0
    edges: int = 0


def write_records(conn: sqlite3.Connection, nodes: list[NodeRecord], edges: list[EdgeRecord]) -> None:
    for node in nodes:
        conn.execute(
            "INSERT OR REPLACE INTO nodes "
            "(id, type, path, name, signature, line_start, line_end, hash, meta) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (node.id, node.type, node.path, node.name, node.signature, node.line_start, node.line_end, node.hash, node.meta),
        )
        conn.execute(
            "INSERT INTO nodes_fts (node_id, name, signature, doc) VALUES (?, ?, ?, ?)",
            (node.id, node.name, node.signature, None),
        )
    for edge in edges:
        conn.execute(
            "INSERT OR REPLACE INTO edges (src, dst, type) VALUES (?, ?, ?)",
            (edge.src, edge.dst, edge.type),
        )


def build_index(root: str | Path, db_path: str | Path) -> IndexStats:
    stats = IndexStats()
    root = Path(root)
    conn = connect(db_path)
    reset(conn)

    for abs_path, relpath in walk_repo(root):
        language_key = detect_language(relpath)
        if language_key is None:
            continue
        try:
            source = abs_path.read_bytes()
            file_nodes, file_edges = extract_file(relpath, source, language_key)
        except (OSError, UnicodeDecodeError, ValueError):
            stats.files_skipped += 1
            continue

        write_records(conn, file_nodes, file_edges)
        conn.execute(
            "INSERT OR REPLACE INTO indexed_files (path, mtime, hash) VALUES (?, ?, ?)",
            (relpath, abs_path.stat().st_mtime, hashlib.sha256(source).hexdigest()),
        )
        stats.files_indexed += 1
        stats.nodes += len(file_nodes)
        stats.edges += len(file_edges)

    spec_nodes, spec_edges = extract_spec_features(root / "spec")
    write_records(conn, spec_nodes, spec_edges)
    stats.nodes += len(spec_nodes)
    stats.edges += len(spec_edges)

    conn.commit()
    conn.close()
    return stats
