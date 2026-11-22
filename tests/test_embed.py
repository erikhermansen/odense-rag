"""Tests af modelpræfikser (uden at indlæse en model)."""

from odense_rag.ingest.embed import EMBEDDING_GEMMA_2, _prompts_for


def test_embeddinggemma_bruger_modelkortets_format() -> None:
    prompts = _prompts_for(EMBEDDING_GEMMA_2)

    assert prompts.query("Hvad koster pas?") == "task: search result | query: Hvad koster pas?"
    assert prompts.passage("Pas\nPriser\n\nEt pas koster 894 kr.") == (
        "title: Pas | text: Priser\n\nEt pas koster 894 kr."
    )


def test_e5_bruger_query_og_passage() -> None:
    prompts = _prompts_for("intfloat/multilingual-e5-large")

    assert prompts.query("x") == "query: x"
    assert prompts.passage("y") == "passage: y"


def test_andre_modeller_faar_teksten_uaendret() -> None:
    prompts = _prompts_for("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    assert prompts.query("x") == "x"
    assert prompts.passage("y") == "y"
