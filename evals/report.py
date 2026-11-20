"""Sammenligning af et eval-resultat med den committede baseline.

Hvert eval-script producerer et "summary": en flad dict {metrik: værdi}.
Den sammenlignes med evals/baseline/<navn>.json, og resultatet skrives som en
markdown-tabel til terminalen og, i GitHub Actions, til jobbets summary-side.
"""

import json
import os
from pathlib import Path

BASELINE_DIR = Path(__file__).parent / "baseline"


def load_baseline(name: str) -> dict[str, float] | None:
    path = BASELINE_DIR / f"{name}.json"
    return json.loads(path.read_text())["metrics"] if path.exists() else None


def save_baseline(name: str, metrics: dict[str, float], config: dict[str, str]) -> Path:
    BASELINE_DIR.mkdir(exist_ok=True)
    path = BASELINE_DIR / f"{name}.json"
    payload = {"config": config, "metrics": metrics}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return path


def compare(
    metrics: dict[str, float],
    baseline: dict[str, float] | None,
    tolerance: float = 0.0,
) -> tuple[str, list[str]]:
    """Returnerer (markdown-tabel, liste af metrikker, der er blevet dårligere).

    Alle metrikker er "højere er bedre". tolerance er, hvor meget en metrik må
    falde, før det tæller som en forværring. Det er 0 for deterministiske evals
    og større for LLM-evals, hvor der er tilfældig variation mellem kørsler.
    """
    lines = ["| Metrik | Baseline | Nu | Ændring |", "|---|---:|---:|---:|"]
    regressions: list[str] = []
    for key, value in metrics.items():
        if baseline is None or key not in baseline:
            lines.append(f"| {key} | - | {value:.3f} | ny |")
            continue
        delta = value - baseline[key]
        if delta < -tolerance - 1e-9:
            marker = "🔻"
            regressions.append(key)
        elif delta > 1e-9:
            marker = "🟢"
        else:
            marker = ""
        lines.append(f"| {key} | {baseline[key]:.3f} | {value:.3f} | {delta:+.3f} {marker} |")
    return "\n".join(lines), regressions


def publish(title: str, body: str) -> None:
    """Printer markdown og skriver det til GitHub Actions' job summary, hvis tilgængelig."""
    text = f"## {title}\n\n{body}\n"
    print(text)
    if summary_file := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary_file, "a") as f:
            f.write(text + "\n")
