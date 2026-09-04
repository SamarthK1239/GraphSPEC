"""Computes and stores node embeddings in the sqlite-vec `vec_nodes` table."""

from __future__ import annotations

import sqlite3

import sqlite_vec

from copilot_graph_spec.embeddings.base import Embedder


def ensure_vec_table(conn: sqlite3.Connection, dimension: int) -> None:
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_nodes USING vec0(node_id TEXT PRIMARY KEY, embedding float[{dimension}])"
    )


def _embedding_text(row: sqlite3.Row) -> str:
    return f"{row['name'] or ''} {row['signature'] or ''}".strip()


def embed_nodes(conn: sqlite3.Connection, embedder: Embedder, batch_size: int = 64, only_missing: bool = True) -> int:
    """Compute and store embeddings. With only_missing=True (default), skips nodes
    that already have a vec_nodes row -- pairs with incremental_index(), which
    purges vec rows for changed/removed nodes, so this naturally re-embeds
    only what changed. Pass only_missing=False to force a full recompute.
    """
    ensure_vec_table(conn, embedder.dimension)

    if only_missing:
        rows = conn.execute(
            "SELECT id, name, signature FROM nodes WHERE id NOT IN (SELECT node_id FROM vec_nodes)"
        ).fetchall()
    else:
        rows = conn.execute("SELECT id, name, signature FROM nodes").fetchall()
    count = 0
    for i in range(0, len(rows), batch_size):
        batch = [r for r in rows[i : i + batch_size] if _embedding_text(r)]
        if not batch:
            continue
        vectors = embedder.embed([_embedding_text(r) for r in batch])
        ids = [r["id"] for r in batch]
        # vec0 virtual tables don't honor INSERT OR REPLACE conflict resolution
        # (raises UNIQUE constraint failed instead) -- delete first, then insert.
        conn.execute(f"DELETE FROM vec_nodes WHERE node_id IN ({','.join('?' * len(ids))})", ids)
        conn.executemany(
            "INSERT INTO vec_nodes (node_id, embedding) VALUES (?, ?)",
            [(r["id"], sqlite_vec.serialize_float32(v)) for r, v in zip(batch, vectors, strict=True)],
        )
        count += len(batch)

    conn.commit()
    return count
