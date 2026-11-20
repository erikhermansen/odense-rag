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

## 2026-11-20 - Korpus udvidet fra 25 til 1.774 sider

Hele /borger/-sektionen fra sitemap'et, undtagen afgørelser, dispensationer og
høringer om enkeltsager (95 sider). 36 tomme navigationssider sprunget over.
Resultat: 1.774 dokumenter, 8,1 MB markdown, 7.432 chunks. Ingest: ca. 2,5 min. (CPU).

**Eval-sættet efter udvidelsen.** Alle out_of_scope-cases blev tjekket mod det nye korpus:
- `oos-boligstoette` var nu besvarbar (boligstoette.md) og blev flyttet til answerable
  som `boligstoette-ansoegning`. Den blev erstattet af `oos-toemningsdag`.
- `oos-byraadsmoede` og `oos-antal-byraadsmedlemmer` blev sværere: korpusset nævner
  tidligere byrådsmøder og "Seniorrådet består af 15 medlemmer". De er nu fælder.
- `flytning-frist-boede`: tjekliste-ved-flytning og navn-og-adresse har også
  5-dagesfristen og bøden (ikke beløbet), så de blev tilføjet som accepterede dokumenter.

**Retrieval faldt som ventet**, med flere sider, der ligner hinanden (24 cases, k=5):

| Variant | hit@1 | hit@3 | hit@5 | MRR |
|---|---:|---:|---:|---:|
| Vektor (uændret system) | 0.792 | 0.833 | 0.917 | 0.833 |
| Vektor, højst 2 chunks pr. dokument | 0.792 | 0.833 | 0.958 | 0.844 |
| Hybrid (vektor + dansk fuldtekst, RRF), intet df-filter | 0.833 | 0.917 | 0.958 | 0.885 |
| Hybrid, ord med df > 10 % udeladt | 0.833 | 0.875 | 0.917 | 0.865 |
| **Hybrid, ord med df > 5 % udeladt (valgt)** | **0.833** | **0.958** | **1.000** | **0.899** |
| Hybrid, ord med df > 2 % udeladt | 0.875 | 1.000 | 1.000 | 0.938 |

Diagnose af fejlene før ændringerne:
- `digital-post-fritagelse-brev`: én lang side (vejledninger-i-brug-af-digital-post)
  fyldte top 4. Løst af grænsen pr. dokument og af hybrid søgning.
- `boligstoette-ansoegning`: siden "Boligstøtte" var ikke i top 8 ved vektorsøgning.
  Hybrid hjalp først, da almindelige ord blev filtreret: Postgres' ts_rank har ingen
  IDF, så "odense" (står i 31 % af chunks) vægtede lige så meget som "boligstøtte" (0,5 %).

**Valg af tærskel: 5 %, ikke 2 %**, selvom 2 % scorer højest. Ved 2 % udelades ord
som "pas" (2,8 %) og "post" (3,3 %), som er kerneord for borgerspørgsmål. At de kan
undværes her, siger mere om 24 cases end om korpusset. At 10 % scorer lavere end
intet filter viser, at forskelle på 1-2 cases er støj ved denne størrelse.

**Determinisme.** En første måling gav hit@3 = 1,000 for den valgte variant, en
senere 0,958. Årsag: uafgjorte placeringer (samme ts_rank) blev ordnet vilkårligt af
row_number(). Rettet med chunk_id som sidste sorteringskriterium; tre kørsler gav
derefter identiske tal. Uden rettelsen ville CI kunne fejle tilfældigt.

**Opstartstid.** Ingest tager nu ca. 2,5 min. Containeren kører `ingest --if-changed`,
der sammenligner et fingeraftryk (skemaversion, chunks, embedding-model) med det
gemte og springer over, hvis intet er ændret: 158 s -> 1,4 s.
