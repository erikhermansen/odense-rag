# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

RAG over Odense Kommune's public citizen-service pages, with citations and evals. The README is in Danish, as are code comments, docstrings, test names and commit messages. Keep it that way. Comments often explain a Python idiom by comparing it to TypeScript, because the author comes from TS.

## Commands

```bash
docker compose up -d db                      # Postgres+pgvector on localhost:5433
uv run odense-rag ingest                     # rebuild index (drops and recreates tables)
uv run odense-rag ask "..."                  # full pipeline; needs ANTHROPIC_API_KEY in .env
uv run odense-rag search "..."               # retrieval only, no LLM
uv run pytest                                # unit tests; no DB or API key needed
uv run pytest tests/test_chunk.py::test_name # single test
uv run ruff check . && uv run ruff format --check . && uv run pyright
uv run python -m evals.retrieval_eval        # deterministic, fails on any regression vs baseline
uv run python -m evals.answer_eval --model anthropic:claude-haiku-5-5   # costs ~$0.50-1 per run
```

Add `--update-baseline` to either eval to accept new numbers. Only do that deliberately, and log the reason in `evals/EXPERIMENTS.md`. Ask before running `answer_eval`, because it spends real money (mostly on the Sonnet judge).

## Architecture

- **Pipeline:** `retrieval.retrieve()` (fixed step, top-k from pgvector) → `agent.answer_question()` (one Pydantic-AI run). Retrieval is deliberately *not* an agent tool, so it can be evaluated in isolation.
- **Output contract:** the LLM returns `Answer | Unknown` (`models.py`) via `NativeOutput`. The model supplies only `chunk_id` + verbatim `quote`. Title, section and URL are looked up from the retrieved chunks. The `@agent.output_validator` in `build_agent` raises `ModelRetry` for unknown chunk ids or non-verbatim quotes.
- **Chunking** (`ingest/chunk.py`) splits on markdown headings. `Chunk.embedding_text` prepends title and heading path (measured to help hit@1). Leaf headings without body text become chunks, because odense.dk sometimes puts the actual information in a heading.
- **Corpus** is a committed snapshot in `data/docs/` (`odense-rag fetch` re-downloads it; never run that in CI). Chunk ids are `<filename-stem>#<n>`, and `evals/dataset.yaml` refers to documents by filename stem.
- **Index metadata:** the embedding model name is stored in `index_meta`. `retrieve()` raises `IndexMismatchError` if `EMBED_MODEL` differs, so re-ingest after changing it.
- **Evals** use pydantic-evals. `evals/cases.py` validates the YAML (it checks that expected docs exist). `answer_eval` passes the whole `EvalCase` as task input, so the LLM judge sees `reference`. Evaluators return `{}` when they don't apply to a case. Per-case details are written to `evals/reports/` (gitignored, and uploaded as a CI artifact).

## Gotchas

- `Settings` is frozen. `lru_cache`d helpers take strings, not `Settings` (see `agent.get_agent`).
- psycopg only accepts literal SQL strings (`LiteralString`). Use `psycopg.sql` for dynamic parts.
- Pydantic-AI 2.x: `result.usage` is a property. Retry feedback reaches the model as a `UserPromptPart` wrapped in `<pyai:retry_feedback>`, not as a `RetryPromptPart`. `TestModel` doesn't support native output, so tests use `FunctionModel(..., profile={"supports_json_schema_output": True})` and emit `{"result": {"kind": "Answer", "data": {...}}}`.
- Load the embedder (`get_embedder`) before running eval cases concurrently. Otherwise every thread loads its own copy.
