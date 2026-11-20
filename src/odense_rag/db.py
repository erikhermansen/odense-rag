"""Postgres med pgvector: skema, indlæsning og søgning."""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from pgvector.psycopg import register_vector
from psycopg import sql

from odense_rag.ingest.chunk import Chunk


# @contextmanager gør en generator til noget, der kan bruges med `with`:
# koden før `yield` er opsætning, koden efter er oprydning.
@contextmanager
def connect(database_url: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(conn)
        yield conn


def recreate_schema(conn: psycopg.Connection, dim: int, embed_model: str) -> None:
    """Dropper og genopretter tabellen.

    Indlæsning er idempotent: hele korpusset bygges forfra hver gang. Med ca.
    60 chunks tager det sekunder, og så kan indeks og data aldrig komme ud af
    trit med hinanden. Embedding-modellen gemmes, så søgning kan opdage, hvis
    der spørges med en anden model end den, korpusset er embeddet med.

    Der er bevidst intet HNSW/IVF-indeks: ved denne størrelse er en eksakt
    sekventiel søgning hurtig og giver det præcise svar. Et ANN-indeks bliver
    først relevant ved titusinder af chunks.
    """
    conn.execute("DROP TABLE IF EXISTS chunks")
    conn.execute("DROP TABLE IF EXISTS index_meta")
    # psycopg accepterer kun literal SQL-strenge (typen LiteralString), så en
    # f-string afvises af type-checkeren. Det er en beskyttelse mod SQL-injection.
    # Dynamiske dele (her vektordimensionen) indsættes eksplicit via psycopg.sql.
    conn.execute(
        sql.SQL(
            """
            CREATE TABLE chunks (
                chunk_id   text PRIMARY KEY,
                doc_id     text NOT NULL,
                title      text NOT NULL,
                url        text NOT NULL,
                section    text NOT NULL,
                text       text NOT NULL,
                embedding  vector({dim}) NOT NULL
            )
            """
        ).format(dim=sql.Literal(dim))
    )
    conn.execute("CREATE TABLE index_meta (embed_model text NOT NULL)")
    conn.execute("INSERT INTO index_meta (embed_model) VALUES (%s)", (embed_model,))


def insert_chunks(
    conn: psycopg.Connection, chunks: list[Chunk], embeddings: list[list[float]]
) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO chunks (chunk_id, doc_id, title, url, section, text, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
            """,
            [
                (c.chunk_id, c.doc_id, c.title, c.url, c.section, c.text, emb)
                for c, emb in zip(chunks, embeddings, strict=True)
            ],
        )


def indexed_embed_model(conn: psycopg.Connection) -> str | None:
    try:
        row = conn.execute("SELECT embed_model FROM index_meta").fetchone()
    except psycopg.errors.UndefinedTable:
        conn.rollback()
        return None
    return row[0] if row else None


def search(
    conn: psycopg.Connection, query_embedding: list[float], k: int
) -> list[tuple[Chunk, float]]:
    """Top-k chunks efter cosinus-lighed (1 - cosinus-afstand)."""
    rows = conn.execute(
        """
        SELECT chunk_id, doc_id, title, url, section, text,
               1 - (embedding <=> %s::vector) AS score
        FROM chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (query_embedding, query_embedding, k),
    ).fetchall()
    # `*row[:6]` spreder de første seks kolonner som argumenter (som ...spread i TS).
    return [(Chunk(*row[:6]), float(row[6])) for row in rows]
