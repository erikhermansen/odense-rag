"""Tests af fjernelse af personoplysninger."""

from pathlib import Path

import pytest

from odense_rag.ingest.pii import scrub_pii

DOCS_DIR = Path(__file__).parents[1] / "data" / "docs"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Mail: frivillig42@gmail.com", "Mail: [e-mail fjernet]"),
        ("Skriv til A.B@Hotmail.DK i dag", "Skriv til [e-mail fjernet] i dag"),
        ("Mobil: +45 22 70 66 20", "Mobil: [nummer fjernet]"),
        ("Mobil. 40162803", "Mobil. [nummer fjernet]"),
        ("CPR: 010190-1234", "CPR: [cpr fjernet]"),
    ],
)
def test_fjerner_private_kontaktoplysninger(text: str, expected: str) -> None:
    assert scrub_pii(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Mail: borgerservice@odense.dk",  # kommunens egne adresser skal bevares
        "Mail: info@rodekors.dk",  # organisationers domæner også
        "Tlf: 66 13 13 72",  # hovednumre skal borgerne kunne finde
        "Sagsnummer 1234567890",  # ti cifre uden bindestreg er ikke et CPR-nummer
        "Betal med MobilePay 12345",
    ],
)
def test_bevarer_offentlige_oplysninger(text: str) -> None:
    assert scrub_pii(text) == text


def test_snapshot_korpus_er_renset() -> None:
    """Fanger det, hvis nogen tilføjer sider uden at køre dem gennem fetch-trinnet."""
    dirty = [p.name for p in DOCS_DIR.glob("*.md") if scrub_pii(p.read_text()) != p.read_text()]

    assert dirty == []
