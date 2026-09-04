"""CLI entry point (click/typer) for copilot-graph-spec: index, serve, etc. (Phase 1/2)."""

import time
from pathlib import Path

import click

from copilot_graph_spec.config import resolve_path
from copilot_graph_spec.db import connect
from copilot_graph_spec.embeddings import embed_nodes, get_embedder
from copilot_graph_spec.indexer import build_index, incremental_index
from copilot_graph_spec.init_cmd import scaffold_project
from copilot_graph_spec.mcp_server import build_server
from copilot_graph_spec.mcp_server.db_queries import vec_table_exists


@click.group()
@click.version_option(package_name="copilot-graph-spec")
def main() -> None:
    """copilot-graph-spec command line interface."""


@main.command("index")
@click.argument("root", type=click.Path(exists=True, file_okay=False), default=None, required=False)
@click.option("--db", "db_path", type=click.Path(), default=None, help="Path to the SQLite graph database.")
@click.option(
    "--incremental",
    is_flag=True,
    default=False,
    help="Only re-parse files whose content changed since the last index, instead of a full rebuild.",
)
def index_command(root: str | None, db_path: str | None, incremental: bool) -> None:
    """Walk ROOT, parse recognized source files, and (re)build the graph database."""
    root = resolve_path("root", root, ".")
    db_path = resolve_path("db", db_path, ".graph/graph.db")
    stats = incremental_index(root, db_path) if incremental else build_index(root, db_path)
    click.echo(
        f"Indexed {stats.files_indexed} files ({stats.files_skipped} skipped, {stats.files_removed} removed) "
        f"-> {stats.nodes} nodes, {stats.edges} edges into {db_path}"
    )


@main.command("embed")
@click.option("--db", "db_path", type=click.Path(), default=None, help="Path to the SQLite graph database.")
@click.option("--backend", default=None, help="Embedder backend: fastembed (default) or sentence-transformers.")
@click.option("--model", "model_name", default=None, help="Override the embedding model name.")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Recompute embeddings for every node, not just ones missing an embedding.",
)
def embed_command(db_path: str | None, backend: str | None, model_name: str | None, force: bool) -> None:
    """Compute embeddings for nodes lacking one (or all, with --force) and store them in vec_nodes."""
    db_path = resolve_path("db", db_path, ".graph/graph.db")
    embedder = get_embedder(backend, model_name)
    conn = connect(db_path)
    try:
        count = embed_nodes(conn, embedder, only_missing=not force)
    finally:
        conn.close()
    click.echo(f"Embedded {count} nodes ({embedder.dimension}-dim) into {db_path}")


@main.command("watch")
@click.argument("root", type=click.Path(exists=True, file_okay=False), default=None, required=False)
@click.option("--db", "db_path", type=click.Path(), default=None, help="Path to the SQLite graph database.")
@click.option("--interval", type=float, default=2.0, help="Polling interval in seconds.")
def watch_command(root: str | None, db_path: str | None, interval: float) -> None:
    """Poll ROOT and incrementally re-index (and re-embed, if embeddings exist) on change."""
    root = resolve_path("root", root, ".")
    db_path = resolve_path("db", db_path, ".graph/graph.db")
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
    default=None,
    help="Repo root that graph_read_span reads files relative to "
    "(default: '.copilot-graph-spec.toml' if present, else parent of copilot_graph_spec/).",
)
@click.option(
    "--db",
    "db_path",
    type=click.Path(),
    default=None,
    help="Path to the SQLite graph database built by `copilot-graph-spec index`.",
)
def serve_command(repo_root: str | None, db_path: str | None) -> None:
    """Run the graph MCP server over stdio."""
    repo_root = resolve_path("root", repo_root, "..")
    db_path = resolve_path("db", db_path, "../.graph/graph.db")
    server = build_server(Path(db_path).resolve(), Path(repo_root).resolve())
    server.run(transport="stdio")


@main.command("init")
@click.argument("target", type=click.Path(file_okay=False), default=".")
@click.option("--force", is_flag=True, default=False, help="Overwrite files that already exist in TARGET.")
def init_command(target: str, force: bool) -> None:
    """Scaffold the GraphSPEC spec-driven workflow (agents, prompts, spec templates, MCP config) into TARGET."""
    report = scaffold_project(Path(target), force=force)
    for rel_path, status in report:
        click.echo(f"{status:9} {rel_path}")


if __name__ == "__main__":
    main()
