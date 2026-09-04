"""SQLite connection helpers for the graph database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec

from graph_mcp.db.schema import SCHEMA


def load_vec_extension(conn: sqlite3.Connection) -> None:
    """Load the sqlite-vec extension so `vec_nodes` (vec0) is usable on this connection."""
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open (creating parent dirs if needed) a connection with the schema applied."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    load_vec_extension(conn)
    conn.executescript(SCHEMA)
    return conn


def reset(conn: sqlite3.Connection) -> None:
    """Clear all rows, used for a full (non-incremental) re-index."""
    conn.execute("DELETE FROM nodes")
    conn.execute("DELETE FROM edges")
    conn.execute("DELETE FROM nodes_fts")
    conn.execute("DELETE FROM indexed_files")
    if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vec_nodes'").fetchone():
        conn.execute("DELETE FROM vec_nodes")
    conn.commit()
