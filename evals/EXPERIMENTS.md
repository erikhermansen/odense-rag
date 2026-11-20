# Eksperimentlog

Kortfattet log over målinger, der ligger til grund for valgene i README'en.
Alle retrieval-tal er fra `uv run python -m evals.retrieval_eval` (22 cases med forventet dokument).

## 2026-11-20 - Titel og afsnit foran chunk-teksten ved embedding

Embedding-model: `paraphrase-multilingual-MiniLM-L12-v2`, k=5, 62 chunks.

| Variant | hit@1 | hit@3 | hit@5 | MRR |
|---|---:|---:|---:|---:|
| Kun brødtekst | 0.818 | 1.000 | 1.000 | 0.902 |
| Titel + overskriftssti + brødtekst (valgt) | 0.909 | 1.000 | 1.000 | 0.955 |

Konklusion: konteksten flytter to cases fra plads 2-3 til plads 1. Uden den
kan en chunk som "prisen er det dobbelte" ikke skelnes mellem pas og kørekort.
Retrieval-evalen fanger forskellen (markeret som forværring mod baseline).
