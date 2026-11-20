"""Tests af chunkeren.

pytest finder automatisk funktioner, der hedder test_*, og bruger almindelig
`assert` i stedet for expect()-kæder. Ved fejl viser pytest begge sider af
sammenligningen.
"""

from pathlib import Path

import pytest

from odense_rag.ingest.chunk import Document, chunk_directory, chunk_document, load_document

DOCS_DIR = Path(__file__).parent.parent / "data" / "docs"


def make_doc(body: str) -> Document:
    return Document(doc_id="test", title="Testside", url="https://example.dk", body=body)


def test_splitter_efter_overskrifter_og_bevarer_stien() -> None:
    doc = make_doc(
        "# Pas\n\nIntro.\n\n## Priser\n\nDyrt.\n\n### Børn\n\nBilligere.\n\n## Tid\n\nHurtigt."
    )

    chunks = chunk_document(doc)

    assert [c.section for c in chunks] == [
        "Pas",
        "Pas > Priser",
        "Pas > Priser > Børn",
        "Pas > Tid",  # "Børn" og "Priser" er lukket, da "Tid" står på niveau 2
    ]
    assert [c.text for c in chunks] == ["Intro.", "Dyrt.", "Billigere.", "Hurtigt."]


def test_springer_tomme_overskrifter_over() -> None:
    chunks = chunk_document(make_doc("# Titel\n\n## Tom\n\n## Med indhold\n\nTekst."))

    assert [c.section for c in chunks] == ["Titel > Med indhold"]


def test_tekst_uden_overskrift_faar_dokumenttitlen_som_afsnit() -> None:
    chunks = chunk_document(make_doc("Bare tekst."))

    assert chunks[0].section == "Testside"


def test_lange_sektioner_splittes_ved_afsnitsgraenser() -> None:
    paragraphs = [f"Afsnit {i}. " + "x" * 80 for i in range(10)]
    doc = make_doc("# Lang\n\n" + "\n\n".join(paragraphs))

    chunks = chunk_document(doc, max_chars=300)

    assert len(chunks) > 1
    assert all(len(c.text) <= 300 for c in chunks)
    # Ingen tekst går tabt eller duplikeres.
    assert "\n\n".join(c.text for c in chunks) == "\n\n".join(paragraphs)


def test_chunk_ids_er_unikke_og_stabile() -> None:
    doc = make_doc("# A\n\nx\n\n## B\n\ny")

    assert [c.chunk_id for c in chunk_document(doc)] == ["test#0", "test#1"]
    assert chunk_document(doc) == chunk_document(doc)


def test_embedding_text_indeholder_titel_og_afsnit() -> None:
    chunk = chunk_document(make_doc("# Pas\n\n## Priser\n\nDet dobbelte."))[0]

    assert chunk.embedding_text.startswith("Testside\nPas > Priser\n\n")


# parametrize kører testen én gang pr. værdi, ligesom test.each i Jest/Vitest.
@pytest.mark.parametrize("path", sorted(DOCS_DIR.glob("*.md")), ids=lambda p: p.stem)
def test_alle_snapshot_dokumenter_kan_indlaeses(path: Path) -> None:
    doc = load_document(path)

    assert doc.title
    assert doc.url.startswith("https://www.odense.dk/")
    assert chunk_document(doc), "dokumentet gav ingen chunks"


def test_korpus_har_unikke_chunk_ids() -> None:
    ids = [c.chunk_id for c in chunk_directory(DOCS_DIR)]

    assert len(ids) == len(set(ids))
