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


def recreate_schema(conn: psycopg.Connection, dim: int, embed_model: str, fingerprint: str) -> None:
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
    conn.execute("DROP TABLE IF EXISTS term_df")
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
                embedding  vector({dim}) NOT NULL,
                -- Dansk fuldtekst (stemming og stopord) til hybrid søgning.
                tsv        tsvector GENERATED ALWAYS AS (
                    to_tsvector('danish', title || ' ' || section || ' ' || text)
                ) STORED
            )
            """
        ).format(dim=sql.Literal(dim))
    )
    conn.execute("CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv)")
    conn.execute("CREATE TABLE index_meta (embed_model text NOT NULL, fingerprint text NOT NULL)")
    conn.execute(
        "INSERT INTO index_meta (embed_model, fingerprint) VALUES (%s, %s)",
        (embed_model, fingerprint),
    )


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


def build_term_stats(conn: psycopg.Connection) -> None:
    """Gemmer, hvor mange chunks hvert (stemmet) ord står i.

    Postgres' ts_rank har ingen IDF: et ord, der står i næsten alle chunks
    ("odense" står i ca. 30 %), vægter lige så meget som et sjældent, præcist
    ord ("boligstøtte", 0,5 %). Tabellen bruges til at udelade de almindelige ord
    fra fuldtekstsøgningen.
    """
    conn.execute("DROP TABLE IF EXISTS term_df")
    conn.execute(
        """
        CREATE TABLE term_df AS
        SELECT word, ndoc, ndoc::float / (SELECT count(*) FROM chunks) AS ratio
        FROM ts_stat('SELECT tsv FROM chunks')
        """
    )
    conn.execute("CREATE UNIQUE INDEX term_df_word_idx ON term_df (word)")


def indexed_fingerprint(conn: psycopg.Connection) -> str | None:
    try:
        row = conn.execute("SELECT fingerprint FROM index_meta").fetchone()
    except psycopg.errors.Error:  # tabellen eller kolonnen findes ikke (ældre indeks)
        conn.rollback()
        return None
    return row[0] if row else None


def indexed_embed_model(conn: psycopg.Connection) -> str | None:
    try:
        row = conn.execute("SELECT embed_model FROM index_meta").fetchone()
    except psycopg.errors.UndefinedTable:
        conn.rollback()
        return None
    return row[0] if row else None


# Hæves, når skemaet ændres, så `ingest --if-changed` bygger indekset forfra.
SCHEMA_VERSION = 2

RRF_K = 60  # standardkonstant i Reciprocal Rank Fusion; dæmper forskellen mellem top-plads


def search(
    conn: psycopg.Connection,
    query_embedding: list[float],
    query_text: str,
    *,
    candidates: int,
    hybrid: bool,
    max_df: float = 0.05,
) -> list[tuple[Chunk, float]]:
    """Kandidat-chunks i rækkefølge, med cosinus-lighed som score.

    Vektorsøgning: de `candidates` nærmeste efter cosinus-afstand.
    Hybrid: derudover de `candidates` bedste efter dansk fuldtekst. De to lister
    flettes med Reciprocal Rank Fusion: hver chunk får sum(1 / (RRF_K + rang))
    over de lister, den optræder i. RRF bruger kun rangen, så de to scores ikke
    skal gøres sammenlignelige.

    Scoren, der returneres, er altid cosinus-lighed, så den betyder det samme
    uanset tilstand. Rækkefølgen er den flettede.
    """
    rows = conn.execute(
        """
        WITH vec AS (
            SELECT chunk_id,
                   row_number() OVER (ORDER BY embedding <=> %(emb)s::vector, chunk_id) AS rnk
            FROM chunks
            ORDER BY embedding <=> %(emb)s::vector, chunk_id
            LIMIT %(n)s
        ),
        -- Spørgsmålets ord stemmes med den danske ordbog. Ord, der står i mere end
        -- max_df af alle chunks, udelades. De resterende ORes sammen.
        kwq AS (
            SELECT to_tsquery('simple', string_agg(quote_literal(t.lex), ' | ')) AS q
            FROM unnest(tsvector_to_array(to_tsvector('danish', %(text)s))) AS t(lex)
            JOIN term_df d ON d.word = t.lex
            WHERE d.ratio <= %(max_df)s
        ),
        kw AS (
            SELECT chunk_id, row_number() OVER (ORDER BY ts_rank_cd(tsv, q) DESC, chunk_id) AS rnk
            FROM chunks, kwq
            WHERE %(hybrid)s AND q IS NOT NULL AND tsv @@ q
            ORDER BY ts_rank_cd(tsv, q) DESC, chunk_id
            LIMIT %(n)s
        ),
        fused AS (
            SELECT chunk_id, sum(1.0 / (%(rrf_k)s + rnk)) AS rrf
            FROM (SELECT * FROM vec UNION ALL SELECT * FROM kw) AS ranked
            GROUP BY chunk_id
        )
        SELECT c.chunk_id, c.doc_id, c.title, c.url, c.section, c.text,
               1 - (c.embedding <=> %(emb)s::vector) AS score
        FROM fused f JOIN chunks c USING (chunk_id)
        -- chunk_id som sidste kriterium: uafgjorte placeringer skal give samme
        -- rækkefølge hver gang, ellers er retrieval-evalen ikke deterministisk.
        ORDER BY f.rrf DESC, score DESC, c.chunk_id
        """,
        {
            "emb": query_embedding,
            "text": query_text,
            "max_df": max_df,
            "n": candidates,
            "hybrid": hybrid,
            "rrf_k": RRF_K,
        },
    ).fetchall()
    # `*row[:6]` spreder de første seks kolonner som argumenter (som ...spread i TS).
    return [(Chunk(*row[:6]), float(row[6])) for row in rows]
