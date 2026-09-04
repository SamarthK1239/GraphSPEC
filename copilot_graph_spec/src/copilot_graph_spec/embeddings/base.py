"""Embedder interface implemented by the fastembed and sentence-transformers backends."""

from __future__ import annotations

from typing import Protocol


class Embedder(Protocol):
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...
