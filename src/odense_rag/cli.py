"""Kommandolinje: `uv run odense-rag --help`.

Typer bygger CLI'en ud fra funktionssignaturer og type hints, lidt ligesom
commander/yargs, men uden at man selv beskriver argumenterne.
"""

import os
from pathlib import Path

import typer

# Pydantic-AI viser et banner om observability (Logfire/OpenTelemetry) i terminalen.
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """RAG over Odense Kommunes offentlige dokumenter."""


@app.command()
def version() -> None:
    """Vis versionen."""
    from importlib.metadata import version as pkg_version

    typer.echo(pkg_version("odense-rag"))


@app.command()
def fetch(
    sources: Path = Path("data/sources.yaml"),
    out: Path = Path("data/docs"),
) -> None:
    """Hent siderne fra odense.dk og gem dem som markdown."""
    from odense_rag.ingest.fetch import fetch_all

    written = fetch_all(sources, out)
    typer.echo(f"{len(written)} dokumenter gemt i {out}/")


@app.command()
def ingest(docs: Path = Path("data/docs")) -> None:
    """Chunk, embed og indlæs dokumenterne i Postgres (bygger indekset forfra)."""
    from odense_rag.config import get_settings
    from odense_rag.retrieval import ingest as run_ingest

    settings = get_settings()
    n = run_ingest(settings, docs)
    typer.echo(f"{n} chunks indlæst med {settings.embed_model}")


@app.command()
def search(query: str, k: int = 5) -> None:
    """Vis top-k chunks for en forespørgsel (uden LLM)."""
    from odense_rag.config import get_settings
    from odense_rag.retrieval import retrieve

    for hit in retrieve(get_settings(), query, k):
        typer.echo(f"{hit.score:.3f}  {hit.chunk.chunk_id:40}  {hit.chunk.section[:60]}")


@app.command()
def ask(question: str) -> None:
    """Stil et spørgsmål og få et svar med kilder."""
    from odense_rag.agent import answer_question
    from odense_rag.config import get_settings

    response = answer_question(get_settings(), question)
    typer.echo(f"\n{response.answer}\n")
    for i, source in enumerate(response.sources, start=1):
        typer.echo(f"[{i}] {source.section}\n    {source.url}")
        typer.echo(f'    "{source.quote}"')
    typer.echo(
        f"\n({response.kind}, {response.model}, {response.latency_ms} ms, "
        f"{response.input_tokens} ind / {response.output_tokens} ud tokens)"
    )


if __name__ == "__main__":
    app()
