"""Opdeler markdown-dokumenter i chunks efter overskrifter.

Valg: siderne på odense.dk er korte (0,4-4 kB) og velstrukturerede med
overskrifter. At splitte efter overskrift giver chunks, der svarer til ét
emne, og overskriften bliver samtidig "afsnit" i kildehenvisningen.
Kun sektioner over MAX_CHARS splittes yderligere, ved afsnitsgrænser.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

MAX_CHARS = 1200
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


# @dataclass genererer __init__, __repr__ og __eq__ ud fra felterne.
# Den bruges til interne værdiobjekter; Pydantic bruges, hvor data krydser en
# grænse (API, LLM, filer) og skal valideres. frozen=True gør den immutable.
@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    url: str
    body: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str  # "<doc_id>#<løbenummer>", stabilt så længe dokumentet er uændret
    doc_id: str
    title: str
    url: str
    section: str  # overskriftssti, fx "Har du mistet dit pas? > Børn under 18 år"
    text: str

    @property
    def embedding_text(self) -> str:
        """Teksten, der embeddes: titel og afsnit foran brødteksten.

        Uden denne kontekst ved en chunk som "Prisen er det dobbelte" ikke,
        om den handler om pas eller kørekort.
        """
        return f"{self.title}\n{self.section}\n\n{self.text}"


def load_document(path: Path) -> Document:
    raw = path.read_text()
    # Tuple-unpacking: `_, a, b = ...` svarer til `const [, a, b] = ...` i TS.
    _, frontmatter, body = raw.split("---\n", 2)
    meta = yaml.safe_load(frontmatter)
    return Document(doc_id=path.stem, title=meta["title"], url=meta["url"], body=body.strip())


def _split_long(text: str, max_chars: int) -> list[str]:
    """Splitter tekst ved afsnitsgrænser, så ingen del overstiger max_chars (hvis muligt)."""
    parts: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            parts.append(current)
            current = para
    if current:
        parts.append(current)
    return parts


def chunk_document(doc: Document, max_chars: int = MAX_CHARS) -> list[Chunk]:
    # Trin 1: saml (overskriftssti, tekst)-par.
    sections: list[tuple[str, str]] = []
    heading_stack: list[tuple[int, str]] = []  # (niveau, overskrift)
    buffer: list[str] = []

    def path_of(stack: list[tuple[int, str]]) -> str:
        return " > ".join(h for _, h in stack) or doc.title

    def flush(next_level: int | None) -> None:
        """Afslutter den aktuelle sektion. next_level er niveauet på den næste overskrift."""
        # En indre funktion kan læse variabler fra den ydre (closure), som i TS.
        text = "\n".join(buffer).strip()
        if text:
            sections.append((path_of(heading_stack), text))
        elif heading_stack and (next_level is None or next_level <= heading_stack[-1][0]):
            # En overskrift uden brødtekst og uden underoverskrifter er et "blad".
            # På odense.dk bærer sådanne overskrifter ofte selve informationen
            # (fx "Så er prisen det dobbelte af normalprisen"), så teksten bevares.
            sections.append((path_of(heading_stack[:-1]), heading_stack[-1][1]))
        buffer.clear()

    for line in doc.body.splitlines():
        if match := HEADING_RE.match(line):  # `:=` tildeler og tester i ét (walrus)
            level, heading = len(match.group(1)), match.group(2).strip()
            flush(level)
            # Fjern overskrifter på samme eller dybere niveau, før den nye skubbes på.
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, heading))
        else:
            buffer.append(line)
    flush(None)

    # Trin 2: split for lange sektioner og nummerér.
    chunks: list[Chunk] = []
    for section, text in sections:
        for part in _split_long(text, max_chars):
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}#{len(chunks)}",
                    doc_id=doc.doc_id,
                    title=doc.title,
                    url=doc.url,
                    section=section,
                    text=part,
                )
            )
    return chunks


def chunk_directory(docs_dir: Path, max_chars: int = MAX_CHARS) -> list[Chunk]:
    return [
        chunk
        for path in sorted(docs_dir.glob("*.md"))
        for chunk in chunk_document(load_document(path), max_chars)
    ]
