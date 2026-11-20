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

## 2026-11-20 - "Blad"-overskrifter blev tabt ved chunking

Første live-spørgsmål ("Hvad koster et nyt pas, hvis jeg har mistet mit gamle?")
gav et svar, der var tro mod kilderne, men forkert: "kilderne nævner ikke en
særlig pris". På odense.dk står "Så er prisen det dobbelte af normalprisen" som en
overskrift uden brødtekst, og chunkeren sprang tomme overskrifter over.

Rettet: en overskrift uden tekst og uden underoverskrifter bliver nu til en chunk
(62 -> 64 chunks). Retrieval-evalen var uændret før og efter, fordi det rigtige
*dokument* blev fundet hele tiden. Fejlen kunne kun ses i svaret.
Lære: retrieval-metrikker på dokumentniveau er ikke nok; svaret skal evalueres.

## 2026-11-20 - Modelsammenligning (svar-eval, 31 cases, effort=low, dommer: Sonnet 5.5)

| | Haiku 5.5 | Opus 5.5 |
|---|---:|---:|
| decision_accuracy | 0.968 | 1.000 |
| correct (besvarbare) | 0.90-0.95 | 1.000 |
| grounded | 0.97-1.00 | 1.000 |
| resisted_injection | 1.000 | 1.000 |
| latens p50 | 2,0 s | 3,5 s |
| pris pr. 1.000 spørgsmål | $0,40 | $18,30 |

Haiku-tallene er fra to kørsler. Første kørsel havde 4 fejlende cases, anden 1, så
variationen mellem kørsler er på størrelse med forskellen mellem modellerne.
Gennemgående fejl hos Haiku: `pas-afhentning-voksen` svarer "ved ikke", selvom
reglen ("over 18 skal selv hente") giver svaret. Det er overforsigtighed, og
prompten ("et forkert svar er værre end intet svar") trækker i den retning.

Opus rammer 100 % på alt. Eval-sættet er derfor for let til at skelne i toppen.
Næste skridt er sværere cases (flere dokumenter, betingede regler, tvetydige spørgsmål).
