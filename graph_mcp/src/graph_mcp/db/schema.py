"""SQLite DDL for the graph database (nodes, edges, nodes_fts).

vec_nodes (sqlite-vec embeddings) is added in Phase 3.
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    path TEXT,
    name TEXT,
    signature TEXT,
    line_start INTEGER,
    line_end INTEGER,
    hash TEXT,
    meta TEXT
);

CREATE TABLE IF NOT EXISTS edges (
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    type TEXT NOT NULL,
    PRIMARY KEY (src, dst, type)
);

CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
CREATE INDEX IF NOT EXISTS idx_nodes_path ON nodes(path);

CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    node_id UNINDEXED,
    name,
    signature,
    doc
);

-- Tracks per-file mtime/content-hash so incremental indexing (Phase 7) can
-- skip unchanged code files without re-parsing them.
CREATE TABLE IF NOT EXISTS indexed_files (
    path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    hash TEXT NOT NULL
);
"""
