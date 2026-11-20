"""Retrieval-eval: får modellen den information, der skal til for at svare?

To niveauer:
- hit@n / MRR: står et forventet *dokument* blandt de n første? (rangering)
- evidence@context: står de ordrette tekststykker, der beviser svaret, i den
  kontekst, modellen faktisk får? Det rigtige dokument kan godt være fundet,
  uden at det afsnit, der bærer svaret, er med. Det er den metrik, der bedst
  forudsiger svarkvaliteten (se evals/EXPERIMENTS.md).

Kører uden LLM og uden API-nøgle, og er deterministisk. Derfor kører den ved
hver push i CI og fejler, hvis en metrik falder i forhold til baseline.

    uv run python -m evals.retrieval_eval                    # sammenlign med baseline
    uv run python -m evals.retrieval_eval --update-baseline  # gem nyt resultat som baseline
    uv run python -m evals.retrieval_eval --context-docs 3   # prøv en variant
"""

import statistics
import sys
from dataclasses import dataclass

import typer
from pydantic import BaseModel
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext, EvaluatorOutput

from evals.cases import EvalCase, load_cases
from evals.report import compare, load_baseline, publish, save_baseline
from odense_rag.config import Settings, get_settings
from odense_rag.ingest.embed import get_embedder
from odense_rag.retrieval import retrieve

BASELINE_NAME = "retrieval"


class RetrievalOutput(BaseModel):
    doc_ids: list[str]  # i rækkefølge efter bedste chunk, uden dubletter
    context: str  # al tekst, modellen ville få (titel, afsnit og brødtekst)
    context_chars: int


def run_retrieval(settings: Settings, question: str) -> RetrievalOutput:
    hits = retrieve(settings, question)
    context = "\n\n".join(f"{h.chunk.title}\n{h.chunk.section}\n{h.chunk.text}" for h in hits)
    return RetrievalOutput(
        # dict.fromkeys bevarer rækkefølgen og fjerner dubletter (som new Set i TS).
        doc_ids=list(dict.fromkeys(h.chunk.doc_id for h in hits)),
        context=context,
        context_chars=sum(len(h.chunk.text) for h in hits),
    )


# En evaluator er en klasse med en evaluate-metode, der får hele konteksten:
# input, output, metadata og varighed. Tal bliver til "scores" i rapporten.
Ctx = EvaluatorContext[str, RetrievalOutput, EvalCase]


@dataclass
class HitAt(Evaluator[str, RetrievalOutput, EvalCase]):
    """Er et af de forventede dokumenter blandt de n første?"""

    n: int

    def get_default_evaluation_name(self) -> str:
        return f"hit@{self.n}"

    def evaluate(self, ctx: Ctx) -> float:
        assert ctx.metadata is not None
        top = ctx.output.doc_ids[: self.n]
        return float(any(doc in ctx.metadata.expected_docs for doc in top))


@dataclass
class ReciprocalRank(Evaluator[str, RetrievalOutput, EvalCase]):
    """1/rang for det første relevante dokument (1.0 hvis det står først, 0 hvis det mangler)."""

    def evaluate(self, ctx: Ctx) -> float:
        assert ctx.metadata is not None
        for rank, doc in enumerate(ctx.output.doc_ids, start=1):
            if doc in ctx.metadata.expected_docs:
                return 1 / rank
        return 0.0


@dataclass
class EvidenceInContext(Evaluator[str, RetrievalOutput, EvalCase]):
    """Står alle evidence-tekststykker i konteksten? (1.0 = ja, 0.0 = mindst ét mangler)"""

    def get_default_evaluation_name(self) -> str:
        return "evidence@context"

    def evaluate(self, ctx: Ctx) -> EvaluatorOutput:
        assert ctx.metadata is not None
        if not ctx.metadata.evidence:
            return {}
        context = ctx.output.context.lower()
        return float(all(phrase.lower() in context for phrase in ctx.metadata.evidence))


def build_dataset() -> Dataset[str, RetrievalOutput, EvalCase]:
    # Kun cases med et forventet dokument giver mening for retrieval.
    cases = [c for c in load_cases() if c.expected_docs]
    return Dataset(
        name="retrieval",
        cases=[Case(name=c.name, inputs=c.question, metadata=c) for c in cases],
        evaluators=[
            *(HitAt(n) for n in (1, 3, 5)),
            ReciprocalRank(),
            EvidenceInContext(),
        ],
    )


def main(
    update_baseline: bool = False,
    mode: str | None = None,
    max_per_doc: int | None = None,
    max_df: float | None = None,
    context_docs: int | None = None,
    context_max_chars: int | None = None,
) -> None:
    base = get_settings()
    # Varianter kan måles fra kommandolinjen uden at ændre .env. None betyder
    # "brug standarden"; 0 er en gyldig værdi, så `or` kan ikke bruges (0 er falsy, som i TS).
    overrides = {
        "retrieval_mode": mode,
        "max_chunks_per_doc": max_per_doc,
        "keyword_max_df": max_df,
        "context_docs": context_docs,
        "context_max_chars": context_max_chars,
    }
    settings = base.model_copy(update={k: v for k, v in overrides.items() if v is not None})
    # Indlæs embedding-modellen én gang, før cases kører parallelt. Ellers
    # indlæser hver tråd sin egen kopi, før lru_cache har nået at gemme den.
    get_embedder(settings.embed_model)

    report = build_dataset().evaluate_sync(lambda q: run_retrieval(settings, q), progress=False)

    averages = report.averages()
    assert averages is not None
    metrics = {
        "evidence@context": averages.scores["evidence@context"],
        **{f"hit@{n}": averages.scores[f"hit@{n}"] for n in (1, 3, 5)},
        "mrr": averages.scores["ReciprocalRank"],
    }
    context_chars = statistics.mean(c.output.context_chars for c in report.cases)
    config = {
        "embed_model": settings.embed_model,
        "top_k": str(settings.top_k),
        "retrieval_mode": settings.retrieval_mode,
        "max_chunks_per_doc": str(settings.max_chunks_per_doc),
        "keyword_max_df": str(settings.keyword_max_df),
        "context_docs": str(settings.context_docs),
        "context_max_chars": str(settings.context_max_chars),
    }

    if update_baseline:
        path = save_baseline(BASELINE_NAME, metrics, config)
        print(f"Baseline gemt i {path}")
        return

    missing_evidence = [
        c.name
        for c in report.cases
        if "evidence@context" in c.scores and not c.scores["evidence@context"].value
    ]
    table, regressions = compare(metrics, load_baseline(BASELINE_NAME))
    variant = ", ".join(f"{k}={v}" for k, v in config.items() if k != "embed_model")
    body = (
        f"Embedding-model: `{settings.embed_model}`\n\n{variant}\n\n{table}\n\n"
        f"Gennemsnitlig kontekst: {context_chars:,.0f} tegn"
    )
    if missing_evidence:
        body += "\n\nEvidence mangler i konteksten: " + ", ".join(
            f"`{m}`" for m in missing_evidence
        )
    publish("Retrieval-eval", body)

    if regressions:
        print(f"FEJL: forværring i {', '.join(regressions)}", file=sys.stderr)
        raise typer.Exit(1)


if __name__ == "__main__":
    typer.run(main)
