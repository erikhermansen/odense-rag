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


if __name__ == "__main__":
    app()
