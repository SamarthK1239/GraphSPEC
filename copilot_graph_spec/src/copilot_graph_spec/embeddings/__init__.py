"""Pluggable embedder interface: fastembed (default) / sentence-transformers (opt-in) (Phase 3)."""

from copilot_graph_spec.embeddings.base import Embedder
from copilot_graph_spec.embeddings.factory import get_embedder
from copilot_graph_spec.embeddings.indexer import embed_nodes, ensure_vec_table

__all__ = ["Embedder", "get_embedder", "embed_nodes", "ensure_vec_table"]
