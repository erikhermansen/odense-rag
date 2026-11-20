"""Tests af udvælgelse af sider og tildeling af dokument-id'er."""

from odense_rag.ingest.fetch import SourceConfig, assign_doc_ids, clean_body, select_urls

PREFIX = "https://www.odense.dk/borger/"

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.odense.dk/borger/borgerservice/pas</loc></url>
  <url><loc>https://www.odense.dk/borger/borgerservice/pas/</loc></url>
  <url><loc>https://www.odense.dk/borger/miljoe/afgoerelser/campusvej-55</loc></url>
  <url><loc>https://www.odense.dk/presse/nyhed</loc></url>
  <url><loc>https://www.odense.dk/borger</loc></url>
</urlset>"""


def test_vaelger_borger_sider_uden_dubletter_og_ekskluderede() -> None:
    config = SourceConfig(sitemap="x", include_prefix=PREFIX, exclude_patterns=["afgoerelse"])

    assert select_urls(SITEMAP, config) == ["https://www.odense.dk/borger/borgerservice/pas"]


def test_doc_id_er_sidste_del_af_stien() -> None:
    url = PREFIX + "borgerservice/pas-online-booking/midlertidigt-pas"

    assert assign_doc_ids([url], PREFIX) == {url: "midlertidigt-pas"}


def test_kolliderende_id_faar_overordnet_mappe_foran() -> None:
    a, b, c = PREFIX + "aeldre/demens", PREFIX + "sundhed/demens", PREFIX + "bolig/flytning"

    ids = assign_doc_ids([a, b, c], PREFIX)

    assert ids == {a: "aeldre--demens", b: "sundhed--demens", c: "flytning"}


def test_kollision_paa_flere_niveauer() -> None:
    a, b = PREFIX + "x/hjaelp/demens", PREFIX + "y/hjaelp/demens"

    assert assign_doc_ids([a, b], PREFIX) == {a: "x--hjaelp--demens", b: "y--hjaelp--demens"}


def test_fjerner_sidefod() -> None:
    assert clean_body("Indhold.\n\nKontaktinformation\n\n66 13 13 72") == "Indhold."
