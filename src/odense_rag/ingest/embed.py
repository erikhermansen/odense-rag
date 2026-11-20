"""Lokale embeddings med fastembed (ONNX, ingen PyTorch og ingen API-nøgle).

At embeddings kører lokalt betyder, at kun genereringstrinnet sender data ud
af huset, og at retrieval-evals kan køre gratis og deterministisk i CI.
"""

from collections.abc import Iterable
from functools import lru_cache

from fastembed import TextEmbedding

CACHE_DIR = ".fastembed_cache"


class Embedder:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name, cache_dir=CACHE_DIR)
        # E5-modellerne er trænet med præfikser og præsterer dårligere uden.
        self._is_e5 = "e5" in model_name.lower()

    @property
    def dim(self) -> int:
        return self._model.embedding_size

    def embed_passages(self, texts: Iterable[str]) -> list[list[float]]:
        if self._is_e5:
            texts = (f"passage: {t}" for t in texts)  # generator: et "lazy" map
        return [vec.tolist() for vec in self._model.embed(list(texts))]

    def embed_query(self, query: str) -> list[float]:
        if self._is_e5:
            query = f"query: {query}"
        return next(iter(self._model.embed([query]))).tolist()


@lru_cache  # én instans pr. modelnavn; modellen er dyr at indlæse
def get_embedder(model_name: str) -> Embedder:
    return Embedder(model_name)
