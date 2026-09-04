"""Default embedder backend: fastembed (ONNX, CPU-only, no PyTorch).

Model is downloaded from Hugging Face on first run and cached for offline use
after that (see README "Locked Decisions").
"""

from __future__ import annotations

from fastembed import TextEmbedding

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class FastEmbedEmbedder:
    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self._model = TextEmbedding(model_name=model_name)
        self.dimension = len(next(iter(self._model.embed(["dimension probe"]))))

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [vec.tolist() for vec in self._model.embed(texts)]
