"""Lokale embeddings med ONNX-modeller (ingen PyTorch og ingen API-nøgle).

At embeddings kører lokalt betyder, at kun genereringstrinnet sender data ud
af huset, og at retrieval-evals kan køre gratis og deterministisk i CI.

De fleste modeller køres med fastembed. EmbeddingGemma 2 er endnu ikke understøttet af
fastembed og køres direkte med ONNX Runtime, som er den motor, fastembed selv bruger.
"""

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import numpy as np
import onnxruntime as ort
from fastembed import TextEmbedding
from huggingface_hub import snapshot_download
from tokenizers import Tokenizer

CACHE_DIR = ".fastembed_cache"

# onnx-community på Hugging Face har konverteret Googles EmbeddingGemma 2 til ONNX.
# Kun tekstdelen bruges, i kvantiseret form (~300 MB i stedet for ~1 GB).
EMBEDDING_GEMMA_2 = "onnx-community/embeddinggemma-2-ONNX"
# En fast version (et commit på Hugging Face), så indeks og evals ikke ændrer sig,
# hvis modellen opdateres.
EMBEDDING_GEMMA_2_REVISION = "daa72c51243991dfcaf9f9137d2c573d8f7790c0"
GEMMA_FILES = ["onnx/model_quantized.onnx", "onnx/model_quantized.onnx_data", "tokenizer.json"]
# Modellen kan læse 8.192 tokens; et tekststykke her er højst ca. 1.200 tegn.
GEMMA_MAX_TOKENS = 2048
GEMMA_DIM = 768


class _Backend(Protocol):
    """Fælles form for de to måder at køre en model på (som et interface i TS)."""

    dim: int

    def embed(self, texts: list[str]) -> Iterator[np.ndarray]: ...


class _FastembedBackend:
    def __init__(self, model_name: str) -> None:
        self._model = TextEmbedding(model_name=model_name, cache_dir=CACHE_DIR)
        self.dim = self._model.embedding_size

    def embed(self, texts: list[str]) -> Iterator[np.ndarray]:
        yield from self._model.embed(texts)


class _GemmaBackend:
    """EmbeddingGemma 2 via ONNX Runtime.

    ONNX-modellen er fælles for tekst, billeder, video og lyd og kræver input for alle
    fire. Til ren tekst sendes tomme billed-, video- og lydinput med.
    """

    def __init__(self) -> None:
        local_dir = Path(
            snapshot_download(
                EMBEDDING_GEMMA_2,
                revision=EMBEDDING_GEMMA_2_REVISION,
                allow_patterns=GEMMA_FILES,
                local_dir=Path(CACHE_DIR) / "embeddinggemma-2-onnx",
            )
        )
        self._tokenizer = Tokenizer.from_file(str(local_dir / "tokenizer.json"))
        self._tokenizer.enable_truncation(GEMMA_MAX_TOKENS)
        pad_id = self._tokenizer.token_to_id("<pad>")
        self._tokenizer.enable_padding(pad_token="<pad>", pad_id=pad_id)
        self._session = ort.InferenceSession(str(local_dir / "onnx" / "model_quantized.onnx"))
        self.dim = GEMMA_DIM

    def embed(self, texts: list[str], batch_size: int = 16) -> Iterator[np.ndarray]:
        empty = np.zeros((0, 512), dtype=np.float32)
        for start in range(0, len(texts), batch_size):
            encodings = self._tokenizer.encode_batch(texts[start : start + batch_size])
            ids = np.array([e.ids for e in encodings], dtype=np.int64)
            mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
            (output,) = self._session.run(
                ["sentence_embedding"],
                {
                    "input_ids": ids,
                    "attention_mask": mask,
                    "image_features": empty,
                    "video_features": empty,
                    "audio_features": empty,
                },
            )
            vectors = np.asarray(output, dtype=np.float32)
            # Normaliseres, så cosinus-afstand i pgvector svarer til modelkortets lighed.
            yield from vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


@dataclass(frozen=True)
class Prompts:
    """Mange embedding-modeller er trænet med faste præfikser og præsterer dårligere uden."""

    query: Callable[[str], str]
    passage: Callable[[str], str]


def _gemma_passage(text: str) -> str:
    # Chunk.embedding_text er "titel\nafsnit\n\ntekst"; modelkortet anbefaler
    # formatet "title: {titel} | text: {indhold}".
    title, _, rest = text.partition("\n")
    return f"title: {title} | text: {rest.strip()}"


def _prompts_for(model_name: str) -> Prompts:
    name = model_name.lower()
    if "embeddinggemma" in name:
        return Prompts(query=lambda q: f"task: search result | query: {q}", passage=_gemma_passage)
    if "e5" in name:
        return Prompts(query=lambda q: f"query: {q}", passage=lambda p: f"passage: {p}")
    # lambda x: x svarer til (x) => x i TS: teksten sendes uændret.
    return Prompts(query=lambda q: q, passage=lambda p: p)


class Embedder:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._backend: _Backend = (
            _GemmaBackend() if model_name == EMBEDDING_GEMMA_2 else _FastembedBackend(model_name)
        )
        self._prompts = _prompts_for(model_name)

    @property
    def dim(self) -> int:
        return self._backend.dim

    def embed_passages(self, texts: Iterable[str]) -> list[list[float]]:
        prepared = [self._prompts.passage(t) for t in texts]
        return [vec.tolist() for vec in self._backend.embed(prepared)]

    def embed_query(self, query: str) -> list[float]:
        return next(self._backend.embed([self._prompts.query(query)])).tolist()


@lru_cache  # én instans pr. modelnavn; modellen er dyr at indlæse
def get_embedder(model_name: str) -> Embedder:
    return Embedder(model_name)
