"""Tests af dokumentgrænsen i retrieval (søgningen selv dækkes af retrieval-evalen)."""

from odense_rag.ingest.chunk import Chunk
from odense_rag.retrieval import limit_per_doc


def hit(doc_id: str, n: int) -> tuple[Chunk, float]:
    chunk = Chunk(f"{doc_id}#{n}", doc_id, doc_id, f"https://x/{doc_id}", doc_id, "tekst")
    return chunk, 1.0 - n / 100


def ids(hits: list[tuple[Chunk, float]]) -> list[str]:
    return [chunk.chunk_id for chunk, _ in hits]


def test_hoejst_n_chunks_fra_samme_dokument() -> None:
    hits = [hit("a", 0), hit("a", 1), hit("a", 2), hit("b", 3), hit("a", 4), hit("c", 5)]

    assert ids(limit_per_doc(hits, k=4, max_per_doc=2)) == ["a#0", "a#1", "b#3", "c#5"]


def test_nul_betyder_ingen_graense() -> None:
    hits = [hit("a", i) for i in range(6)]

    assert ids(limit_per_doc(hits, k=3, max_per_doc=0)) == ["a#0", "a#1", "a#2"]


def test_returnerer_faerre_end_k_hvis_der_ikke_er_nok_dokumenter() -> None:
    hits = [hit("a", i) for i in range(6)]

    assert ids(limit_per_doc(hits, k=5, max_per_doc=2)) == ["a#0", "a#1"]
