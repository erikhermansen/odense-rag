"""Indlæsning af korpus og top-k-søgning.

Retrieval er bevidst et fast, deterministisk trin før LLM-kaldet i stedet for
et tool, agenten selv kalder. Så kan retrieval-kvaliteten måles isoleret og
uden API-nøgle, og et dårligt svar kan spores til enten søgning eller generering.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from odense_rag import db
from odense_rag.config import Settings
from odense_rag.ingest.chunk import Chunk, chunk_directory
from odense_rag.ingest.embed import get_embedder


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float


def corpus_fingerprint(chunks: list[Chunk], embed_model: str) -> str:
    """Hash af alt, der bestemmer indeksets indhold: skema, chunks og embedding-model."""
    digest = hashlib.sha256(f"schema={db.SCHEMA_VERSION}\0{embed_model}".encode())
    for chunk in chunks:
        digest.update(f"{chunk.chunk_id}\0{chunk.embedding_text}\0".encode())
    return digest.hexdigest()


def ingest(settings: Settings, docs_dir: Path, *, if_changed: bool = False) -> int | None:
    """Bygger indekset forfra. Med if_changed springes det over, hvis intet er ændret.

    Returnerer antal chunks, eller None hvis indekset allerede var opdateret.
    """
    chunks = chunk_directory(docs_dir)
    fingerprint = corpus_fingerprint(chunks, settings.embed_model)
    if if_changed:
        with db.connect(settings.database_url) as conn:
            if db.indexed_fingerprint(conn) == fingerprint:
                return None

    embedder = get_embedder(settings.embed_model)
    embeddings = embedder.embed_passages(c.embedding_text for c in chunks)
    with db.connect(settings.database_url) as conn:
        db.recreate_schema(conn, embedder.dim, settings.embed_model, fingerprint)
        db.insert_chunks(conn, chunks, embeddings)
        db.build_term_stats(conn)
    return len(chunks)


class IndexMismatchError(RuntimeError):
    pass


def retrieve(settings: Settings, query: str, k: int | None = None) -> list[RetrievedChunk]:
    embedder = get_embedder(settings.embed_model)
    with db.connect(settings.database_url) as conn:
        indexed = db.indexed_embed_model(conn)
        if indexed != settings.embed_model:
            raise IndexMismatchError(
                f"Indekset er bygget med {indexed!r}, men EMBED_MODEL er "
                f"{settings.embed_model!r}. Kør `odense-rag ingest`."
            )
        k = k or settings.top_k
        hits = db.search(
            conn,
            embedder.embed_query(query),
            query,
            # Hentes der flere kandidater end k, har dokumentgrænsen noget at vælge imellem.
            candidates=max(k * 10, 50),
            hybrid=settings.retrieval_mode == "hybrid",
            max_df=settings.keyword_max_df,
        )
    return [
        RetrievedChunk(chunk, score)
        for chunk, score in limit_per_doc(hits, k, settings.max_chunks_per_doc)
    ]


def limit_per_doc(
    hits: list[tuple[Chunk, float]], k: int, max_per_doc: int
) -> list[tuple[Chunk, float]]:
    """De første k hits, med højst max_per_doc fra samme dokument (0 = ingen grænse).

    Uden grænsen kan én lang side fylde hele top-k og skubbe andre relevante
    sider ud, fx når et spørgsmål kræver information fra to sider.
    """
    if max_per_doc <= 0:
        return hits[:k]
    per_doc: dict[str, int] = {}
    selected: list[tuple[Chunk, float]] = []
    for chunk, score in hits:
        if per_doc.get(chunk.doc_id, 0) < max_per_doc:
            selected.append((chunk, score))
            per_doc[chunk.doc_id] = per_doc.get(chunk.doc_id, 0) + 1
            if len(selected) == k:
                break
    return selected
