"""Builds the graph-mcp MCPServer and registers the 8 graph_* tools.

Each tool opens a short-lived SQLite connection (SQLite connections aren't
shared safely across the worker threads the MCP SDK dispatches sync tools
onto) and returns pointers (ids/paths/line spans/signatures) rather than
file bodies -- callers fetch exact spans on demand via `graph_read_span`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from graph_mcp.db import load_vec_extension
from graph_mcp.embeddings import Embedder, get_embedder
from graph_mcp.mcp_server import db_queries
from graph_mcp.mcp_server.read_span import read_span


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    load_vec_extension(conn)
    return conn


def build_server(db_path: Path, repo_root: Path) -> MCPServer:
    server = MCPServer(
        "graph-mcp",
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
    def graph_search(query: str, limit: int = 20) -> dict:
        """Lexical (FTS5) + vector hybrid search over symbols/files, fused via RRF.

        Falls back to lexical-only until `graph-mcp embed` has populated vectors.
        """
        conn = _connect(db_path)
        try:
            embedder = _cached_embedder() if db_queries.vec_table_exists(conn) else None
            return {"results": db_queries.hybrid_search(conn, query, embedder, limit)}
        except sqlite3.Error as exc:
            return {"error": str(exc)}
        finally:
            conn.close()

    @server.tool()
    def graph_file_outline(path: str) -> dict:
        """Symbol map of a file (signatures + line spans), no bodies."""
        conn = _connect(db_path)
        try:
            return {"symbols": db_queries.file_outline(conn, path)}
        except sqlite3.Error as exc:
            return {"error": str(exc)}
        finally:
            conn.close()

    @server.tool()
    def graph_get_symbol(node_id: str) -> dict:
        """Signature / location / doc metadata only for a single node (no body)."""
        conn = _connect(db_path)
        try:
            node = db_queries.get_symbol(conn, node_id)
            return node if node is not None else {"error": f"no such node: {node_id}"}
        except sqlite3.Error as exc:
            return {"error": str(exc)}
        finally:
            conn.close()

    @server.tool()
    def graph_neighbors(node_id: str, direction: str = "both", edge_types: list[str] | None = None) -> dict:
        """Callers/callees/imports/references of a node. direction: in | out | both."""
        conn = _connect(db_path)
        try:
            return db_queries.neighbors(conn, node_id, direction, edge_types)
        except sqlite3.Error as exc:
            return {"error": str(exc)}
        finally:
            conn.close()

    @server.tool()
    def graph_impact(node_id: str, max_depth: int = 2) -> dict:
        """Blast radius: nodes that transitively depend on/call/import node_id."""
        conn = _connect(db_path)
        try:
            return {"impacted": db_queries.impact(conn, node_id, max_depth)}
        except sqlite3.Error as exc:
            return {"error": str(exc)}
        finally:
            conn.close()

    @server.tool()
    def graph_subgraph(seed_ids: list[str], max_nodes: int = 50, max_depth: int = 2) -> dict:
        """Focused, token-budgeted slice of the graph around seed node ids."""
        conn = _connect(db_path)
        try:
            return db_queries.subgraph(conn, seed_ids, max_nodes, max_depth)
        except sqlite3.Error as exc:
            return {"error": str(exc)}
        finally:
            conn.close()

    @server.tool()
    def graph_read_span(path: str, line_start: int, line_end: int) -> dict:
        """Fetch the exact source text for a line range (max 500 lines)."""
        try:
            text = read_span(repo_root, path, line_start, line_end)
            return {"path": path, "line_start": line_start, "line_end": line_end, "text": text}
        except (ValueError, FileNotFoundError, OSError) as exc:
            return {"error": str(exc)}

    @server.tool()
    def graph_trace(node_id: str | None = None) -> dict:
        """Spec <-> requirement <-> task <-> symbol traceability + coverage gaps.

        Pass node_id for its trace neighbors, or omit it to list coverage gaps.
        """
        conn = _connect(db_path)
        try:
            return db_queries.trace(conn, node_id)
        except sqlite3.Error as exc:
            return {"error": str(exc)}
        finally:
            conn.close()

    return server
