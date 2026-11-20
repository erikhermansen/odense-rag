"""HTTP-API: POST /ask og GET /health.

    uv run uvicorn odense_rag.api:app --reload

FastAPI bruger de samme Pydantic-modeller til at validere request-body og
generere OpenAPI-dokumentation (se /docs), lidt ligesom tRPC + Zod.
"""

import logging
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pydantic_ai.exceptions import (
    ModelConnectionError,
    ModelRateLimitError,
    ModelServerError,
    ModelUnavailableError,
)

from odense_rag import db
from odense_rag.agent import answer_question
from odense_rag.config import Settings, get_settings
from odense_rag.models import AskResponse
from odense_rag.retrieval import IndexMismatchError

logger = logging.getLogger("odense_rag")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(
    title="odense-rag",
    description="Spørgsmål og svar om Odense Kommunes borgerservice, med kildehenvisninger.",
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


# Midlertidige fejl hos sprogmodellen: forbindelse og timeout, overbelastning, rate
# limit og serverfejl. En forkert API-nøgle er derimod en konfigurationsfejl og
# skal ikke maskeres som "prøv igen".
TRANSIENT_MODEL_ERRORS = (
    ModelConnectionError,
    ModelRateLimitError,
    ModelServerError,
    ModelUnavailableError,
)

# Annotated[Settings, Depends(...)] er FastAPI's dependency injection. I tests
# kan get_settings udskiftes via app.dependency_overrides.
SettingsDep = Annotated[Settings, Depends(get_settings)]


# `def` (ikke `async def`): answer_question er synkron og blokerende, så FastAPI
# kører den i en trådpulje i stedet for at blokere event-loopet.
@app.post("/ask")
def ask(request: AskRequest, settings: SettingsDep) -> AskResponse:
    try:
        response = answer_question(settings, request.question)
    except IndexMismatchError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except TRANSIENT_MODEL_ERRORS as e:
        # Sprogmodellen er utilgængelig eller overbelastet. Det er midlertidigt,
        # så klienten får 503 ("prøv igen") frem for en generisk 500.
        logger.warning("Sprogmodellen svarede ikke: %s", e)
        raise HTTPException(status_code=503, detail="Sprogmodellen svarer ikke lige nu.") from e

    # Strukturerede logs: én linje pr. kald med de tal, drift har brug for.
    # Selve spørgsmålet logges ikke, da borgere kan skrive personoplysninger.
    logger.info(
        "ask kind=%s model=%s latency_ms=%d input_tokens=%d output_tokens=%d sources=%d",
        response.kind,
        response.model,
        response.latency_ms,
        response.input_tokens,
        response.output_tokens,
        len(response.sources),
    )
    return response


class Health(BaseModel):
    status: str
    embed_model: str | None


@app.get("/health")
def health(settings: SettingsDep) -> Health:
    try:
        with db.connect(settings.database_url) as conn:
            indexed = db.indexed_embed_model(conn)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"database utilgængelig: {e}") from e
    if indexed is None:
        raise HTTPException(status_code=503, detail="indeks mangler; kør `odense-rag ingest`")
    return Health(status="ok", embed_model=indexed)


# Den byggede Vue-frontend (frontend/dist) serveres fra roden, hvis den findes.
# Den monteres til sidst, så /ask, /health og /docs matches først.
FRONTEND_DIST = Path(__file__).parents[2] / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
