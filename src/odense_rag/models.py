"""Pydantic-skemaer for LLM-output og API-svar.

Der er to lag:
- LLM-output (`Answer` | `Unknown`): det, modellen skal udfylde. Det er så
  smalt som muligt, så der er mindst muligt at gøre forkert. Modellen angiver
  kun chunk_id og et citat, aldrig URL'er eller titler.
- API-svar (`AskResponse`): det, klienten får. Kilderne slås op ud fra
  chunk_id, så URL og afsnit altid kommer fra databasen, ikke fra modellen.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    chunk_id: str = Field(description="Id på kilden, præcis som angivet i <kilde id=...>.")
    quote: str = Field(
        description="Et kort ordret citat (højst én sætning) fra kilden, der understøtter svaret."
    )


class Answer(BaseModel):
    """Et svar, der er understøttet af de udleverede kilder."""

    kind: Literal["answer"] = "answer"
    answer: str = Field(description="Svaret på dansk, i klart sprog, kort og præcist.")
    citations: list[Citation] = Field(min_length=1)


class Unknown(BaseModel):
    """Bruges, når kilderne ikke indeholder svaret, eller spørgsmålet ligger uden for opgaven."""

    kind: Literal["unknown"] = "unknown"
    reason: str = Field(
        description=(
            "Kort forklaring på dansk til borgeren om, hvorfor du ikke kan svare. "
            "Må ikke indeholde et svar på spørgsmålet; kan du svare, så brug answer."
        )
    )


# Discriminated union på feltet `kind`, præcis som z.discriminatedUnion("kind", [...]).
LLMOutput = Annotated[Answer | Unknown, Field(discriminator="kind")]


class Source(BaseModel):
    chunk_id: str
    title: str
    section: str
    url: str
    quote: str


class RetrievedSource(BaseModel):
    """Et af de tekststykker, retrieval fandt. Gør RAG-trinnet synligt i frontend og evals."""

    chunk_id: str
    title: str
    section: str
    url: str
    text: str
    score: float = Field(description="Cosinus-lighed med spørgsmålet (højere er mere relevant).")
    cited: bool = Field(description="Om svaret citerer dette tekststykke.")


class AskResponse(BaseModel):
    kind: Literal["answer", "unknown"]
    answer: str
    sources: list[Source]
    retrieved: list[RetrievedSource]
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
