"""Henter sider fra odense.dk og gemmer dem som markdown med frontmatter.

Hvilke sider der hentes, styres af data/sources.yaml: alle URL'er i sitemap'et
under et prefix, minus dem der matcher et ekskluderingsmønster.

Snapshot'et committes til repoet, så evals er reproducerbare, også selvom
odense.dk ændrer sig. Fetch køres manuelt, ikke i CI. Allerede hentede sider
springes over, så en afbrudt kørsel kan genoptages.
"""

import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from pathlib import Path

import httpx
import trafilatura
import yaml
from pydantic import BaseModel

USER_AGENT = "odense-rag-demo/0.1 (offentligt demoprojekt; respekterer robots.txt)"
MIN_BODY_CHARS = 100  # kortere sider er typisk rene navigationssider


class SourceConfig(BaseModel):
    sitemap: str
    include_prefix: str
    exclude_patterns: list[str] = []


def select_urls(sitemap_xml: str, config: SourceConfig) -> list[str]:
    root = ET.fromstring(sitemap_xml)
    # Sitemaps bruger et XML-namespace; "{*}" matcher et vilkårligt namespace
    # (virker i XPath-metoderne som iterfind, ikke i iter).
    urls = [el.text.strip().rstrip("/") for el in root.iterfind(".//{*}loc") if el.text]
    excluded = re.compile("|".join(config.exclude_patterns)) if config.exclude_patterns else None
    selected = {
        url
        for url in urls
        if url.startswith(config.include_prefix.rstrip("/") + "/")
        and not (excluded and excluded.search(url))
    }
    return sorted(selected)


def assign_doc_ids(urls: list[str], prefix: str) -> dict[str, str]:
    """URL -> dokument-id: sidste del af stien, med overordnede mapper foran ved kollision.

    'borger/borgerservice/pas-online-booking/midlertidigt-pas' -> 'midlertidigt-pas'
    To sider, der begge ender på 'demens', bliver til fx 'aeldre--demens' og 'sundhed--demens'.
    """
    parts = {url: url.removeprefix(prefix).strip("/").split("/") for url in urls}
    depth = dict.fromkeys(urls, 1)
    while True:
        ids = {url: "--".join(parts[url][-depth[url] :]) for url in urls}
        counts = Counter(ids.values())
        colliding = [u for u in urls if counts[ids[u]] > 1 and depth[u] < len(parts[u])]
        if not colliding:
            return ids
        for url in colliding:
            depth[url] += 1


def to_markdown(html: str) -> tuple[str, str] | None:
    """Uddrager (titel, brødtekst som markdown) fra en side, eller None hvis den er tom."""
    metadata = trafilatura.extract_metadata(html)
    body = trafilatura.extract(
        html,
        output_format="markdown",
        include_tables=True,
        include_links=False,
        include_images=False,
        include_comments=False,
    )
    if not body:
        return None
    title = metadata.title if metadata and metadata.title else ""
    # Fjern sitets suffiks, fx "Pas | Odense Kommune" -> "Pas".
    title = title.split("|")[0].strip()
    return title, clean_body(body)


# Overskriften står nogle gange som "## Kontaktinformation", andre gange uden "#".
FOOTER_RE = re.compile(r"^#*\s*Kontaktinformation\s*$", re.MULTILINE)


def clean_body(body: str) -> str:
    """Fjerner den fælles sidefod og overflødigt whitespace.

    Sidefoden (telefon og adresse på Borgernes Hus) er identisk på alle sider.
    Bliver den i korpusset, matcher den mange forespørgsler lige godt og
    skubber de relevante chunks ned i resultatlisten.
    """
    body = FOOTER_RE.split(body, maxsplit=1)[0]
    # List comprehension: som .map() og .filter() i ét udtryk.
    lines = [" ".join(line.split()) if line.strip() else "" for line in body.splitlines()]
    text = "\n".join(lines)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip()


def fetch_all(
    sources_file: Path, out_dir: Path, *, delay_s: float = 0.5, refetch: bool = False
) -> list[Path]:
    # Pydantic validerer YAML'en på samme måde som Zod ville validere JSON.
    config = SourceConfig.model_validate(yaml.safe_load(sources_file.read_text()))
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    skipped: list[str] = []

    # `with` er Pythons svar på try/finally med automatisk oprydning:
    # klienten lukkes, når blokken forlades, også ved en exception.
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        sitemap = client.get(config.sitemap, timeout=60)
        sitemap.raise_for_status()
        urls = select_urls(sitemap.text, config)
        doc_ids = assign_doc_ids(urls, config.include_prefix)
        print(f"{len(urls)} sider valgt fra sitemap")

        for i, url in enumerate(urls, start=1):
            path = out_dir / f"{doc_ids[url]}.md"  # `/` på Path-objekter samler stier
            if path.exists() and not refetch:
                written.append(path)
                continue
            try:
                response = client.get(url, timeout=20)
                response.raise_for_status()
            except httpx.HTTPError as e:
                skipped.append(f"{url} ({e.__class__.__name__})")
                continue
            finally:
                time.sleep(delay_s)  # vær høflig over for serveren, også ved fejl

            extracted = to_markdown(response.text)
            if extracted is None or len(extracted[1]) < MIN_BODY_CHARS:
                skipped.append(f"{url} (tom eller navigationsside)")
                continue
            title, body = extracted
            frontmatter = yaml.safe_dump(
                {"title": title, "url": url, "fetched": date.today().isoformat()},
                allow_unicode=True,
                sort_keys=False,
            )
            path.write_text(f"---\n{frontmatter}---\n\n{body}\n")
            written.append(path)
            if i % 100 == 0:
                print(f"  {i}/{len(urls)} ...")

    print(f"{len(skipped)} sider sprunget over")
    (out_dir.parent / "skipped.txt").write_text("\n".join(skipped) + "\n")
    return written
