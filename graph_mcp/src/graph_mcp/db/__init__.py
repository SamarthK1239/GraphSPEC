"""SQLite schema and access layer for nodes/edges/nodes_fts/vec_nodes (Phase 1)."""

from graph_mcp.db.connection import connect, load_vec_extension, reset
from graph_mcp.db.schema import SCHEMA

__all__ = ["connect", "load_vec_extension", "reset", "SCHEMA"]
