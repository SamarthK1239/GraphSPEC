"""Pluggable embedder interface: fastembed (default) / sentence-transformers (opt-in) (Phase 3)."""

from graph_mcp.embeddings.base import Embedder
from graph_mcp.embeddings.factory import get_embedder
from graph_mcp.embeddings.indexer import embed_nodes, ensure_vec_table

__all__ = ["Embedder", "get_embedder", "embed_nodes", "ensure_vec_table"]
