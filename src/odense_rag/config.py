"""Typed konfiguration fra miljøvariabler og .env.

Svarer til at parse `process.env` med et Zod-skema: felterne valideres og
konverteres ved opstart, så resten af koden kan stole på typerne.
"""

from functools import lru_cache

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


# @lru_cache på en funktion uden argumenter er Pythons gængse "lazy singleton":
# første kald bygger objektet, alle senere kald returnerer det samme.
@lru_cache
def get_settings() -> Settings:
    return Settings()
