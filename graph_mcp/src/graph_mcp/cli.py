"""CLI entry point (click/typer) for graph-mcp: index, serve, etc. (Phase 1/2)."""

import time
from pathlib import Path

import click

from graph_mcp.db import connect
from graph_mcp.embeddings import embed_nodes, get_embedder
from graph_mcp.indexer import build_index, incremental_index
from graph_mcp.mcp_server import build_server
from graph_mcp.mcp_server.db_queries import vec_table_exists


@click.group()
@click.version_option(package_name="graph-mcp")
def main() -> None:
    """graph-mcp command line interface."""


@main.command("index")
@click.argument("root", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--db", "db_path", type=click.Path(), default=".graph/graph.db", help="Path to the SQLite graph database.")
@click.option(
    "--incremental",
    is_flag=True,
    default=False,
    help="Only re-parse files whose content changed since the last index, instead of a full rebuild.",
)
def index_command(root: str, db_path: str, incremental: bool) -> None:
    """Walk ROOT, parse recognized source files, and (re)build the graph database."""
    stats = incremental_index(root, db_path) if incremental else build_index(root, db_path)
    click.echo(
        f"Indexed {stats.files_indexed} files ({stats.files_skipped} skipped, {stats.files_removed} removed) "
        f"-> {stats.nodes} nodes, {stats.edges} edges into {db_path}"
    )


@main.command("embed")
@click.option("--db", "db_path", type=click.Path(), default=".graph/graph.db", help="Path to the SQLite graph database.")
@click.option("--backend", default=None, help="Embedder backend: fastembed (default) or sentence-transformers.")
@click.option("--model", "model_name", default=None, help="Override the embedding model name.")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Recompute embeddings for every node, not just ones missing an embedding.",
)
def embed_command(db_path: str, backend: str | None, model_name: str | None, force: bool) -> None:
    """Compute embeddings for nodes lacking one (or all, with --force) and store them in vec_nodes."""
    embedder = get_embedder(backend, model_name)
    conn = connect(db_path)
    try:
        count = embed_nodes(conn, embedder, only_missing=not force)
    finally:
        conn.close()
    click.echo(f"Embedded {count} nodes ({embedder.dimension}-dim) into {db_path}")


@main.command("watch")
@click.argument("root", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--db", "db_path", type=click.Path(), default=".graph/graph.db", help="Path to the SQLite graph database.")
@click.option("--interval", type=float, default=2.0, help="Polling interval in seconds.")
def watch_command(root: str, db_path: str, interval: float) -> None:
    """Poll ROOT and incrementally re-index (and re-embed, if embeddings exist) on change."""
    embedder_cache: list = []

    def cached_embedder():
        if not embedder_cache:
            embedder_cache.append(get_embedder())
        return embedder_cache[0]

    click.echo(f"Watching {root} every {interval}s (Ctrl+C to stop)...")
    try:
        while True:
            stats = incremental_index(root, db_path)
            if stats.files_indexed or stats.files_removed:
                click.echo(
                    f"Re-indexed {stats.files_indexed} changed files ({stats.files_removed} removed) "
                    f"-> {stats.nodes} nodes, {stats.edges} edges"
                )
                conn = connect(db_path)
                try:
                    if vec_table_exists(conn):
                        embedded = embed_nodes(conn, cached_embedder(), only_missing=True)
                        if embedded:
                            click.echo(f"Re-embedded {embedded} nodes")
                finally:
                    conn.close()
            time.sleep(interval)
    except KeyboardInterrupt:
        click.echo("Stopped watching.")


@main.command("serve")
@click.option(
    "--root",
    "repo_root",
    type=click.Path(exists=True, file_okay=False),
    default="..",
    help="Repo root that graph_read_span reads files relative to (default: parent of graph_mcp/).",
)
@click.option(
    "--db",
    "db_path",
    type=click.Path(),
    default="../.graph/graph.db",
    help="Path to the SQLite graph database built by `graph-mcp index`.",
)
def serve_command(repo_root: str, db_path: str) -> None:
    """Run the graph MCP server over stdio."""
    server = build_server(Path(db_path).resolve(), Path(repo_root).resolve())
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
