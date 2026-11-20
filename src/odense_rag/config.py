"""Typed konfiguration fra miljøvariabler og .env.

Svarer til at parse `process.env` med et Zod-skema: felterne valideres og
konverteres ved opstart, så resten af koden kan stole på typerne.
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)

    # SecretStr skjuler værdien i repr() og logs; .get_secret_value() henter den.
    anthropic_api_key: SecretStr | None = None
    database_url: str = "postgresql://odense:odense@localhost:5433/odense_rag"
    llm_model: str = "anthropic:claude-opus-5-5"
    # Hvor meget modellen tænker, før den svarer: low | medium | high.
    # Spørgsmål-svar over korte kilder kræver sjældent dyb ræsonnering.
    llm_effort: str = "low"
    embed_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    top_k: int = 5
    # Retrieval: "vector" (kun embeddings) eller "hybrid" (embeddings + dansk fuldtekst).
    # Hybrid valgt ud fra retrieval-evalen på det fulde korpus (se evals/EXPERIMENTS.md).
    retrieval_mode: Literal["vector", "hybrid"] = "hybrid"
    # Ord, der står i mere end denne andel af alle chunks, udelades af fuldtekstsøgningen.
    keyword_max_df: float = 0.05
    # Højst så mange chunks fra samme dokument i top-k (0 = ingen grænse).
    max_chunks_per_doc: int = 2


# @lru_cache på en funktion uden argumenter er Pythons gængse "lazy singleton":
# første kald bygger objektet, alle senere kald returnerer det samme.
@lru_cache
def get_settings() -> Settings:
    return Settings()
