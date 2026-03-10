# Nexen Profiler

This repo contains an offline-first user profiling system plus a local demo dataset.

## Layout

- `app/` — application code
- `data/` — user activity data
  - `write/` — user-produced artifacts
  - `read/` — user-consumed/saved content
  - `browse/` — optional browsing history (`history.csv`)
- `docker/` — Dockerfiles
- `prototypes/` — roles and prototype assets
- `tests/` — tests

## Quick Start (Local, SQLite)

```bash
python -m app.pipeline.run_pipeline
```

## Local Dev (Conda)

```bash
conda env create -f environment.yml
conda activate nexen-profiler
python -m app.pipeline.run_pipeline
```

Defaults:
- `DATA_DIR` defaults to `data/` if present, otherwise the repo root.
- If `write/` and `read/` exist under `DATA_DIR`, they define sources.
- `browse/history.csv` is treated as browse history (fallback: `history.csv` at `DATA_DIR`).
- File extensions are only used to choose a parser/content type, not to assign source.
- Profile markdown is written to a timestamped filename (e.g. `profile_20260305_142233.md`) to avoid overwrites.
- LLM reasoning and Gemini embeddings are required; the pipeline errors if they are unavailable.

Environment variables:
- `DATA_DIR`: directory holding the `write/read/browse` files (or flat directory).
- `DB_URL`: SQLAlchemy DB URL (default: `sqlite:///user_profiler.db`).
- `USER_ID`: profile key (default: `default_user`).
- `EMBEDDING_DIM`: embedding vector size for storage (default: `768`).
- `GEMINI_EMBED_MODEL`: Gemini embedding model name (default: `gemini-embedding-001`).
- `GEMINI_EMBED_BATCH`: embedding batch size (default: `100`).
- `PROFILE_LANG`: output language for portrait text (`en` or `zh`, default: `zh`).
- `PROFILE_MD_PATH`: output path for profile markdown. If it is a directory, a timestamped filename is created inside it. If it is a `.md` file, the timestamp is inserted before the extension.

## Docker (Postgres + pgvector)

```bash
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
