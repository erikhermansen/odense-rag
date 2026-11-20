"""Kommandolinje: `uv run odense-rag --help`.

Typer bygger CLI'en ud fra funktionssignaturer og type hints, lidt ligesom
commander/yargs, men uden at man selv beskriver argumenterne.
"""

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


if __name__ == "__main__":
    app()
