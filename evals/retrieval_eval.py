"""Retrieval-eval: findes det rigtige dokument blandt de hentede chunks?

Kører uden LLM og uden API-nøgle, og er deterministisk. Derfor kører den ved
hver push i CI og fejler, hvis en metrik falder i forhold til baseline.

    uv run python -m evals.retrieval_eval                    # sammenlign med baseline
    uv run python -m evals.retrieval_eval --update-baseline  # gem nyt resultat som baseline
"""

import sys
from dataclasses import dataclass

import typer
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from evals.cases import EvalCase, load_cases
from evals.report import compare, load_baseline, publish, save_baseline
from odense_rag.config import get_settings
from odense_rag.ingest.embed import get_embedder
from odense_rag.retrieval import retrieve

BASELINE_NAME = "retrieval"


def ranked_doc_ids(question: str, k: int) -> list[str]:
    """Dokument-id'er i rækkefølge efter bedste chunk, uden dubletter."""
    hits = retrieve(get_settings(), question, k)
    # dict.fromkeys bevarer rækkefølgen og fjerner dubletter (som new Set i TS).
    return list(dict.fromkeys(h.chunk.doc_id for h in hits))


# En evaluator er en klasse med en evaluate-metode, der får hele konteksten:
# input, output, metadata og varighed. bool-resultater bliver til "assertions"
# (bestået/ikke bestået), float-resultater bliver til "scores".
@dataclass
class HitAt(Evaluator[str, list[str], EvalCase]):
    """Er et af de forventede dokumenter blandt de n første?"""

    n: int

    def get_default_evaluation_name(self) -> str:
        return f"hit@{self.n}"

    def evaluate(self, ctx: EvaluatorContext[str, list[str], EvalCase]) -> float:
        assert ctx.metadata is not None
        # Returneres som float (score) frem for bool (assertion), så flere
        # hit@n-værdier kan stå side om side i rapporten.
        return float(any(doc in ctx.metadata.expected_docs for doc in ctx.output[: self.n]))


@dataclass
class ReciprocalRank(Evaluator[str, list[str], EvalCase]):
    """1/rang for det første relevante dokument (1.0 hvis det står først, 0 hvis det mangler)."""

    def evaluate(self, ctx: EvaluatorContext[str, list[str], EvalCase]) -> float:
        assert ctx.metadata is not None
        for rank, doc in enumerate(ctx.output, start=1):
            if doc in ctx.metadata.expected_docs:
                return 1 / rank
        return 0.0


def build_dataset(k: int) -> Dataset[str, list[str], EvalCase]:
    # Kun cases med et forventet dokument giver mening for retrieval.
    cases = [c for c in load_cases() if c.expected_docs]
    return Dataset(
        name="retrieval",
        cases=[Case(name=c.name, inputs=c.question, metadata=c) for c in cases],
        evaluators=[*(HitAt(n) for n in sorted({1, 3, k})), ReciprocalRank()],
    )


def main(update_baseline: bool = False, k: int | None = None) -> None:
    settings = get_settings()
    k = k or settings.top_k
    dataset = build_dataset(k)
    # Indlæs embedding-modellen én gang, før cases kører parallelt. Ellers
    # indlæser hver tråd sin egen kopi, før lru_cache har nået at gemme den.
    get_embedder(settings.embed_model)

    report = dataset.evaluate_sync(lambda q: ranked_doc_ids(q, k), progress=False)
    report.print(include_input=False, include_output=True, include_durations=False)

    averages = report.averages()
    assert averages is not None
    metrics = {name: averages.scores[name] for name in averages.scores if name.startswith("hit@")}
    metrics["mrr"] = averages.scores["ReciprocalRank"]
    config = {"embed_model": settings.embed_model, "top_k": str(k)}

    if update_baseline:
        path = save_baseline(BASELINE_NAME, metrics, config)
        print(f"Baseline gemt i {path}")
        return

    misses = [c.name for c in report.cases if not c.scores[f"hit@{k}"].value]
    table, regressions = compare(metrics, load_baseline(BASELINE_NAME))
    body = f"Embedding-model: `{settings.embed_model}`, k={k}\n\n{table}"
    if misses:
        body += "\n\nIkke fundet i top-k: " + ", ".join(f"`{m}`" for m in misses)
    publish("Retrieval-eval", body)

    if regressions:
        print(f"FEJL: forværring i {', '.join(regressions)}", file=sys.stderr)
        raise typer.Exit(1)


if __name__ == "__main__":
    typer.run(main)
