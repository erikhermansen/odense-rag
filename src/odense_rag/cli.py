"""Kommandolinje: `uv run odense-rag --help`.

Typer bygger CLI'en ud fra funktionssignaturer og type hints, lidt ligesom
commander/yargs, men uden at man selv beskriver argumenterne.
"""

from pathlib import Path

import typer

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


if __name__ == "__main__":
    app()
