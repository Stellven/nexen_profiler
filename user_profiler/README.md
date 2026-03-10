# Offline User Profiler (MVP)

This project ingests local `write/`, `read/`, and optional `browse/` data and produces a profile JSON with explainable evidence links.

## Quick Start (Local, SQLite)

```bash
cd user_profiler
python -m app.pipeline.run_pipeline
```

## Local Dev (Conda)

```bash
cd ..
conda env create -f environment.yml
conda activate nexen-profiler
cd user_profiler
python -m app.pipeline.run_pipeline
```

Defaults:
- `DATA_DIR` defaults to `data/` if present, otherwise the repo root (one level above `user_profiler/`).
- If `write/` and `read/` exist under `DATA_DIR`, they define sources.
- `browse/history.csv` is treated as browse history (fallback: `history.csv` at `DATA_DIR`).
- File extensions are only used to choose a parser/content type, not to assign source.
- Profile markdown is written to a timestamped filename (e.g. `profile_20260305_142233.md`) to avoid overwrites.
- LLM reasoning and Gemini embeddings are required; the pipeline errors if they are unavailable.

Environment variables:
- `DATA_DIR`: directory holding the `write/read/browse` files (or flat directory).
- `DB_URL`: SQLAlchemy DB URL (default: `sqlite:///user_profiler.db`).
- `USER_ID`: profile key (default: `default_user`).
- `EMBEDDING_DIM`: embedding vector size for storage (default: `768`). Must match the embedding model output size.
- `GEMINI_EMBED_MODEL`: Gemini embedding model name (default: `gemini-embedding-001`).
- `GEMINI_EMBED_BATCH`: embedding batch size (default: `100`).
- `PROFILE_LANG`: output language for portrait text (`en` or `zh`, default: `en`).
- `PROFILE_MD_PATH`: output path for profile markdown. If it is a directory, a timestamped filename is created inside it. If it is a `.md` file, the timestamp is inserted before the extension.
- `ACTION_SIGNAL_MODE`: action extraction mode (`rules` or `llm`, default: `rules`).
- `ACTION_LLM_MIN_CONF`: minimum confidence for LLM actions (default: `0.45`).
- `ACTION_LLM_MAX_CHARS`: max characters sent to LLM per event (default: `2400`).
- `ACTION_LLM_MAX_LABELS`: max actions returned by LLM per event (default: `4`).
- `INTENT_MODE`: project intent inference mode (`rules` or `llm`, default: `rules`).

## Docker (Postgres + pgvector)

```bash
cd ..
docker compose up --build
```

The API will be available at `http://localhost:8000`:
- `GET /profile/{user_id}`
- `GET /profile/{user_id}/explain/{item_id}`

## Notes
- The pipeline parses all HTML locally.
- LLM calls are handled via Gemini in `app/llm/gemini_client.py`.
- Embeddings use Gemini (google-genai).
- Signals and inferences enforce evidence links. Inferences without evidence are dropped.
- Switching action extraction modes does not backfill existing signals. To recompute actions, clear the database or use a new `USER_ID`.
- If you change `EMBEDDING_DIM`, delete the SQLite DB (or use a new `DB_URL`) before rerunning so the schema matches.
