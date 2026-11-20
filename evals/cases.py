"""Indlæsning og validering af evals/dataset.yaml.

Datasættet valideres med Pydantic ved indlæsning. En stavefejl i en kategori
eller et expected_doc, der ikke findes, giver en fejl med det samme i stedet
for et forkert tal i rapporten.
"""

from enum import StrEnum
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, model_validator

ROOT = Path(__file__).parent.parent
DATASET_PATH = ROOT / "evals" / "dataset.yaml"
DOCS_DIR = ROOT / "data" / "docs"


# StrEnum: medlemmerne er også strenge, så de kan sammenlignes med og
# serialiseres som "answerable" osv. Svarer til en string-union i TS.
class Category(StrEnum):
    ANSWERABLE = "answerable"
    OUT_OF_SCOPE = "out_of_scope"
    INJECTION = "injection"


class EvalCase(BaseModel):
    name: str
    category: Category
    question: str
    expected_docs: list[str] = []
    reference: str | None = None
    # Tekst, der plantes som en ekstra kilde ved siden af de hentede chunks.
    # Bruges til at teste indirekte prompt injection (instruktioner i et dokument).
    planted_chunk: str | None = None

    @model_validator(mode="after")
    def check_consistency(self) -> Self:
        if self.category is Category.ANSWERABLE and not (self.expected_docs and self.reference):
            raise ValueError(f"{self.name}: answerable kræver expected_docs og reference")
        if self.category is Category.OUT_OF_SCOPE and self.expected_docs:
            raise ValueError(f"{self.name}: out_of_scope må ikke have expected_docs")
        return self

    @property
    def should_answer(self) -> bool:
        """Skal systemet give et svar (frem for "ved ikke")?"""
        return bool(self.expected_docs)


class EvalDataset(BaseModel):
    cases: list[EvalCase]

    @model_validator(mode="after")
    def check_docs_exist(self) -> Self:
        known = {p.stem for p in DOCS_DIR.glob("*.md")}
        for case in self.cases:
            # Set-differens: dokumenter i expected_docs, der ikke findes i korpusset.
            if missing := set(case.expected_docs) - known:
                raise ValueError(f"{case.name}: ukendte dokumenter {sorted(missing)}")
        names = [c.name for c in self.cases]
        if len(names) != len(set(names)):
            raise ValueError("Case-navne skal være unikke")
        return self


def load_cases(path: Path = DATASET_PATH) -> list[EvalCase]:
    return EvalDataset.model_validate(yaml.safe_load(path.read_text())).cases
