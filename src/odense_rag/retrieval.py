"""Indlæsning af korpus og top-k-søgning.

Retrieval er bevidst et fast, deterministisk trin før LLM-kaldet i stedet for
et tool, agenten selv kalder. Så kan retrieval-kvaliteten måles isoleret og
uden API-nøgle, og et dårligt svar kan spores til enten søgning eller generering.
"""

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


def ingest(settings: Settings, docs_dir: Path) -> int:
    chunks = chunk_directory(docs_dir)
    embedder = get_embedder(settings.embed_model)
    embeddings = embedder.embed_passages(c.embedding_text for c in chunks)

    with db.connect(settings.database_url) as conn:
        db.recreate_schema(conn, embedder.dim, settings.embed_model)
        db.insert_chunks(conn, chunks, embeddings)
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
        hits = db.search(conn, embedder.embed_query(query), k or settings.top_k)
    return [RetrievedChunk(chunk, score) for chunk, score in hits]
