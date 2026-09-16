"""Builds the copilot-graph-spec MCPServer and registers the 8 graph_* tools.

Each tool opens a short-lived SQLite connection (SQLite connections aren't
shared safely across the worker threads the MCP SDK dispatches sync tools
onto) and returns pointers (ids/paths/line spans/signatures) rather than
file bodies -- callers fetch exact spans on demand via `graph_read_span`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from copilot_graph_spec.db import load_vec_extension
from copilot_graph_spec.embeddings import Embedder, get_embedder
from copilot_graph_spec.mcp_server import db_queries
from copilot_graph_spec.mcp_server.read_span import read_span


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    load_vec_extension(conn)
    return conn


def _trim(items: list[dict], limit: int) -> tuple[list[dict], bool]:
    """Slice back down to `limit` items, reporting whether anything was cut."""
    if len(items) <= limit:
        return items, False
    return items[:limit], True


def build_server(db_path: Path, repo_root: Path) -> MCPServer:
    server = MCPServer(
        "copilot-graph-spec",
        instructions=(
            "Query the code + spec graph for pointers (path, line span, signature) "
            "instead of reading whole files. Use graph_search/graph_file_outline/"
            "graph_get_symbol/graph_neighbors/graph_impact/graph_subgraph/graph_trace "
            "to locate what you need, then graph_read_span to fetch only that span."
        ),
    )

    # Lazily built on first search that has embeddings available, so a server
    # backed by a lexical-only index never pays fastembed's model-load cost.
    embedder_cache: list[Embedder] = []

    def _cached_embedder() -> Embedder:
        if not embedder_cache:
            embedder_cache.append(get_embedder())
        return embedder_cache[0]

    @server.tool()
    def graph_search(query: str, limit: int = 20, fields: list[str] | None = None) -> dict:
        """Lexical (FTS5) + vector hybrid search over symbols/files, fused via RRF.

        Falls back to lexical-only until `copilot-graph-spec embed` has populated vectors.
        Pass `fields` (e.g. ["id","name","path"]) to shrink each result to just those keys.
        """
        conn = _connect(db_path)
        try:
            embedder = _cached_embedder() if db_queries.vec_table_exists(conn) else None
            results = db_queries.hybrid_search(conn, query, embedder, limit)
            return {"results": db_queries.project_list(results, fields)}
        except sqlite3.Error as exc:
            return {"error": str(exc)}
        finally:
            conn.close()

    @server.tool()
    def graph_file_outline(path: str, limit: int = 300, fields: list[str] | None = None) -> dict:
        """Symbol map of a file (signatures + line spans), no bodies."""
        conn = _connect(db_path)
        try:
            symbols, truncated = _trim(db_queries.file_outline(conn, path, limit + 1), limit)
            return {"symbols": db_queries.project_list(symbols, fields), "truncated": truncated}
        except sqlite3.Error as exc:
            return {"error": str(exc)}
        finally:
            conn.close()

    @server.tool()
    def graph_get_symbol(node_id: str, fields: list[str] | None = None) -> dict:
        """Signature / location / doc metadata only for a single node (no body)."""
        conn = _connect(db_path)
        try:
            node = db_queries.get_symbol(conn, node_id)
            if node is None:
                return {"error": f"no such node: {node_id}"}
            return db_queries.project(node, fields)
        except sqlite3.Error as exc:
            return {"error": str(exc)}
        finally:
            conn.close()

    @server.tool()
    def graph_neighbors(
        node_id: str,
        direction: str = "both",
        edge_types: list[str] | None = None,
        limit: int = 200,
        fields: list[str] | None = None,
    ) -> dict:
        """Callers/callees/imports/references of a node. direction: in | out | both."""
        conn = _connect(db_path)
        try:
            result = db_queries.neighbors(conn, node_id, direction, edge_types, limit + 1)
            outgoing, out_truncated = _trim(result["outgoing"], limit)
            incoming, in_truncated = _trim(result["incoming"], limit)
            return {
                "outgoing": db_queries.project_list(outgoing, fields),
                "incoming": db_queries.project_list(incoming, fields),
                "truncated": out_truncated or in_truncated,
            }
        except sqlite3.Error as exc:
            return {"error": str(exc)}
        finally:
            conn.close()

    @server.tool()
    def graph_impact(
        node_id: str, max_depth: int = 2, max_results: int = 300, fields: list[str] | None = None
    ) -> dict:
        """Blast radius: nodes that transitively depend on/call/import node_id."""
        conn = _connect(db_path)
        try:
            impacted, truncated = _trim(db_queries.impact(conn, node_id, max_depth, max_results + 1), max_results)
            return {"impacted": db_queries.project_list(impacted, fields), "truncated": truncated}
        except sqlite3.Error as exc:
            return {"error": str(exc)}
        finally:
            conn.close()

    @server.tool()
    def graph_subgraph(
        seed_ids: list[str], max_nodes: int = 50, max_depth: int = 2, fields: list[str] | None = None
    ) -> dict:
        """Focused, token-budgeted slice of the graph around seed node ids."""
        conn = _connect(db_path)
        try:
            result = db_queries.subgraph(conn, seed_ids, max_nodes, max_depth)
            return {**result, "nodes": db_queries.project_list(result["nodes"], fields)}
        except sqlite3.Error as exc:
            return {"error": str(exc)}
        finally:
            conn.close()

    @server.tool()
    def graph_read_span(path: str, line_start: int, line_end: int) -> dict:
        """Fetch source text for a line range. Spans over 500 lines are truncated;
        check `truncated`/`next_line_start` in the response to fetch the remainder.
        """
        try:
            result = read_span(repo_root, path, line_start, line_end)
            return {"path": path, "line_start": line_start, **result}
        except (ValueError, FileNotFoundError, OSError) as exc:
            return {"error": str(exc)}

    @server.tool()
    def graph_trace(node_id: str | None = None, limit: int = 300) -> dict:
        """Spec <-> requirement <-> task <-> symbol traceability + coverage gaps.

        Pass node_id for its trace neighbors, or omit it to list coverage gaps.
        """
        conn = _connect(db_path)
        try:
            result = db_queries.trace(conn, node_id, limit + 1)
            if node_id is not None:
                outgoing, out_truncated = _trim(result["outgoing"], limit)
                incoming, in_truncated = _trim(result["incoming"], limit)
                return {"outgoing": outgoing, "incoming": incoming, "truncated": out_truncated or in_truncated}
            gaps, truncated = _trim(result["coverage_gaps"], limit)
            return {"coverage_gaps": gaps, "truncated": truncated}
        except sqlite3.Error as exc:
            return {"error": str(exc)}
        finally:
            conn.close()

    return server
