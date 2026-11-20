"""Henter siderne i data/sources.yaml og gemmer dem som markdown med frontmatter.

Snapshot'et committes til repoet, så evals er reproducerbare, også selvom
odense.dk ændrer sig. Fetch køres manuelt, ikke i CI.
"""

import re
import time
from datetime import date
from pathlib import Path

import httpx
import trafilatura
import yaml
from pydantic import BaseModel

USER_AGENT = "odense-rag-demo/0.1 (offentligt demoprojekt; respekterer robots.txt)"


class SourceList(BaseModel):
    base_url: str
    pages: list[str]


def slug_for(path: str) -> str:
    """'borgerservice/pas-online-booking/midlertidigt-pas' -> 'midlertidigt-pas'."""
    return path.rstrip("/").split("/")[-1]


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


def fetch_all(sources_file: Path, out_dir: Path, delay_s: float = 1.0) -> list[Path]:
    # Pydantic validerer YAML'en på samme måde som Zod ville validere JSON.
    sources = SourceList.model_validate(yaml.safe_load(sources_file.read_text()))
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # `with` er Pythons svar på try/finally med automatisk oprydning:
    # klienten lukkes, når blokken forlades, også ved en exception.
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for page in sources.pages:
            url = sources.base_url + page
            response = client.get(url, timeout=20)
            response.raise_for_status()

            extracted = to_markdown(response.text)
            if extracted is None:
                print(f"SPRINGER OVER (tom side): {url}")
                continue
            title, body = extracted

            frontmatter = yaml.safe_dump(
                {"title": title, "url": url, "fetched": date.today().isoformat()},
                allow_unicode=True,
                sort_keys=False,
            )
            path = out_dir / f"{slug_for(page)}.md"  # `/` på Path-objekter samler stier
            path.write_text(f"---\n{frontmatter}---\n\n{body}\n")
            written.append(path)
            print(f"OK  {path.name}  ({len(body)} tegn)")
            time.sleep(delay_s)  # vær høflig over for serveren

    return written
