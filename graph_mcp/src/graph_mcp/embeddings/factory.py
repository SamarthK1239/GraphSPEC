"""Selects an embedder backend by name, defaulting to fastembed.

Configurable via args or the GRAPH_MCP_EMBED_BACKEND / GRAPH_MCP_EMBED_MODEL
env vars so the model stays swappable without code changes.
"""

from __future__ import annotations

import os

from graph_mcp.embeddings.base import Embedder

BACKENDS = ("fastembed", "sentence-transformers")


def get_embedder(backend: str | None = None, model_name: str | None = None) -> Embedder:
    backend = backend or os.environ.get("GRAPH_MCP_EMBED_BACKEND", "fastembed")
    model_name = model_name or os.environ.get("GRAPH_MCP_EMBED_MODEL")

    if backend == "fastembed":
        from graph_mcp.embeddings.fastembed_backend import DEFAULT_MODEL, FastEmbedEmbedder

        return FastEmbedEmbedder(model_name or DEFAULT_MODEL)
    if backend == "sentence-transformers":
        from graph_mcp.embeddings.sentence_transformers_backend import (
            DEFAULT_MODEL,
            SentenceTransformerEmbedder,
        )

        return SentenceTransformerEmbedder(model_name or DEFAULT_MODEL)
    raise ValueError(f"unknown embedder backend {backend!r}; expected one of {BACKENDS}")
