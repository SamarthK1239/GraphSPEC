"""Read-only query functions over the graph SQLite database.

Kept free of any MCP-specific types so they can be unit tested directly
against a sqlite3.Connection.
"""

from __future__ import annotations

import json
import sqlite3

import sqlite_vec

from graph_mcp.embeddings.base import Embedder

RRF_K = 60

EDGE_TYPES = {
    "imports",
    "calls",
    "references",
    "contains",
    "derives",
    "implements",
    "covers",
    "depends_on",
}
TRACE_EDGE_TYPES = {"derives", "implements", "covers", "depends_on"}
IMPACT_EDGE_TYPES = {"calls", "imports", "references", "depends_on", "implements", "derives", "covers"}


def _row_to_node(row: sqlite3.Row) -> dict:
    meta = row["meta"]
    return {
        "id": row["id"],
        "type": row["type"],
        "path": row["path"],
        "name": row["name"],
        "signature": row["signature"],
        "line_start": row["line_start"],
        "line_end": row["line_end"],
        "meta": json.loads(meta) if meta else {},
    }


def _fts_query(query: str) -> str:
    """Quote each token so arbitrary user input can't break FTS5 query syntax."""
    tokens = query.split()
    if not tokens:
        return '""'
    return " ".join('"' + tok.replace('"', '""') + '"' for tok in tokens)


def search(conn: sqlite3.Connection, query: str, limit: int = 20) -> list[dict]:
    limit = max(1, min(limit, 100))
    rows = conn.execute(
        "SELECT n.* FROM nodes_fts f JOIN nodes n ON n.id = f.node_id "
        "WHERE nodes_fts MATCH ? ORDER BY rank LIMIT ?",
        (_fts_query(query), limit),
    ).fetchall()
    return [_row_to_node(r) for r in rows]


def vec_table_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'vec_nodes'").fetchone()
    return row is not None


def _fts_candidate_ids(conn: sqlite3.Connection, query: str, pool_size: int) -> list[str]:
    rows = conn.execute(
        "SELECT node_id FROM nodes_fts WHERE nodes_fts MATCH ? ORDER BY rank LIMIT ?",
        (_fts_query(query), pool_size),
    ).fetchall()
    return [r["node_id"] for r in rows]


def _vector_candidate_ids(conn: sqlite3.Connection, embedder: Embedder, query: str, pool_size: int) -> list[str]:
    vector = embedder.embed([query])[0]
    rows = conn.execute(
        "SELECT node_id FROM vec_nodes WHERE embedding MATCH ? AND k = ? ORDER BY distance",
        (sqlite_vec.serialize_float32(vector), pool_size),
    ).fetchall()
    return [r["node_id"] for r in rows]


def _rrf_fuse(*ranked_id_lists: list[str], k: int = RRF_K) -> list[str]:
    """Reciprocal-rank fusion: combine several rankings into one, favoring ids that rank well in any of them."""
    scores: dict[str, float] = {}
    for ranked_ids in ranked_id_lists:
        for rank, node_id in enumerate(ranked_ids, start=1):
            scores[node_id] = scores.get(node_id, 0.0) + 1.0 / (k + rank)
    return [node_id for node_id, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]


def hybrid_search(conn: sqlite3.Connection, query: str, embedder: Embedder | None, limit: int = 20) -> list[dict]:
    """FTS5 lexical search, fused via RRF with vector similarity when embeddings are available.

    Falls back to lexical-only results when `embedder` is None or `vec_nodes`
    hasn't been populated yet (i.e. before `graph-mcp embed` has run).
    """
    limit = max(1, min(limit, 100))
    pool_size = max(limit * 3, 50)

    lexical_ids = _fts_candidate_ids(conn, query, pool_size)
    if embedder is None or not vec_table_exists(conn):
        fused_ids = lexical_ids[:limit]
    else:
        vector_ids = _vector_candidate_ids(conn, embedder, query, pool_size)
        fused_ids = _rrf_fuse(lexical_ids, vector_ids)[:limit]

    nodes = [get_symbol(conn, node_id) for node_id in fused_ids]
    return [n for n in nodes if n is not None]


def file_outline(conn: sqlite3.Connection, path: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM nodes WHERE path = ? AND type = 'symbol' ORDER BY line_start",
        (path,),
    ).fetchall()
    return [_row_to_node(r) for r in rows]


def get_symbol(conn: sqlite3.Connection, node_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    return _row_to_node(row) if row else None


def neighbors(
    conn: sqlite3.Connection,
    node_id: str,
    direction: str = "both",
    edge_types: list[str] | None = None,
) -> dict:
    types = [t for t in (edge_types or []) if t in EDGE_TYPES] or None
    result: dict[str, list[dict]] = {"outgoing": [], "incoming": []}

    if direction in ("out", "both"):
        q = "SELECT e.type AS edge_type, n.* FROM edges e JOIN nodes n ON n.id = e.dst WHERE e.src = ?"
        params: list = [node_id]
        if types:
            q += f" AND e.type IN ({','.join('?' * len(types))})"
            params.extend(types)
        rows = conn.execute(q, params).fetchall()
        result["outgoing"] = [{"edge_type": r["edge_type"], **_row_to_node(r)} for r in rows]

    if direction in ("in", "both"):
        q = "SELECT e.type AS edge_type, n.* FROM edges e JOIN nodes n ON n.id = e.src WHERE e.dst = ?"
        params = [node_id]
        if types:
            q += f" AND e.type IN ({','.join('?' * len(types))})"
            params.extend(types)
        rows = conn.execute(q, params).fetchall()
        result["incoming"] = [{"edge_type": r["edge_type"], **_row_to_node(r)} for r in rows]

    return result


def impact(conn: sqlite3.Connection, node_id: str, max_depth: int = 2) -> list[dict]:
    """Blast radius: nodes that (transitively) depend on/call/import node_id."""
    max_depth = max(1, min(max_depth, 5))
    visited = {node_id}
    frontier = [node_id]
    results: list[dict] = []

    for depth in range(1, max_depth + 1):
        if not frontier:
            break
        placeholders = ",".join("?" * len(frontier))
        edge_placeholders = ",".join("?" * len(IMPACT_EDGE_TYPES))
        rows = conn.execute(
            f"SELECT DISTINCT n.* FROM edges e JOIN nodes n ON n.id = e.src "
            f"WHERE e.dst IN ({placeholders}) AND e.type IN ({edge_placeholders})",
            [*frontier, *IMPACT_EDGE_TYPES],
        ).fetchall()
        next_frontier = []
        for row in rows:
            if row["id"] in visited:
                continue
            visited.add(row["id"])
            results.append({**_row_to_node(row), "depth": depth})
            next_frontier.append(row["id"])
        frontier = next_frontier

    return results


def subgraph(conn: sqlite3.Connection, seed_ids: list[str], max_nodes: int = 50, max_depth: int = 2) -> dict:
    max_nodes = max(1, min(max_nodes, 200))
    max_depth = max(0, min(max_depth, 5))

    nodes_by_id: dict[str, dict] = {}
    edges: set[tuple[str, str, str]] = set()

    for sid in seed_ids:
        node = get_symbol(conn, sid)
        if node:
            nodes_by_id[sid] = node

    frontier = list(nodes_by_id.keys())
    depth = 0
    while frontier and depth < max_depth and len(nodes_by_id) < max_nodes:
        placeholders = ",".join("?" * len(frontier))
        rows = conn.execute(
            f"SELECT src, dst, type FROM edges WHERE src IN ({placeholders}) OR dst IN ({placeholders})",
            [*frontier, *frontier],
        ).fetchall()
        next_frontier: list[str] = []
        for row in rows:
            edges.add((row["src"], row["dst"], row["type"]))
            for candidate in (row["src"], row["dst"]):
                if candidate not in nodes_by_id and len(nodes_by_id) < max_nodes:
                    node = get_symbol(conn, candidate)
                    if node:
                        nodes_by_id[candidate] = node
                        next_frontier.append(candidate)
        frontier = next_frontier
        depth += 1

    return {
        "nodes": list(nodes_by_id.values()),
        "edges": [{"src": s, "dst": d, "type": t} for s, d, t in edges if s in nodes_by_id and d in nodes_by_id],
    }


def trace(conn: sqlite3.Connection, node_id: str | None = None) -> dict:
    """Spec <-> requirement <-> task <-> symbol traceability + coverage gaps.

    With `node_id`: returns its derives/implements/covers/depends_on neighbors.
    Without: reports requirement/plan_item nodes with no incoming
    covers/implements/derives edge (coverage gaps). Tasks are excluded here
    since they're always the *source* of covers/implements edges, never the
    target -- a task with no incoming edge isn't a gap, it's expected.
    """
    if node_id is not None:
        return neighbors(conn, node_id, direction="both", edge_types=list(TRACE_EDGE_TYPES))

    rows = conn.execute(
        "SELECT * FROM nodes WHERE type IN ('requirement', 'plan_item') "
        "AND id NOT IN (SELECT dst FROM edges WHERE type IN ('covers', 'implements', 'derives'))"
    ).fetchall()
    return {"coverage_gaps": [_row_to_node(r) for r in rows]}
