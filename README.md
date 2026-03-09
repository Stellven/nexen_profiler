# Nexen Profiler

This repo contains an offline-first user profiling system plus a local demo dataset.

## Layout

- `user_profiler/` — application code, tests, prototypes, Dockerfiles
- `data/` — user activity data
  - `write/` — user-produced artifacts
  - `read/` — user-consumed/saved content
  - `browse/` — optional browsing history (`history.csv`)

## Quick Start (Local, SQLite)

```bash
cd user_profiler
python -m app.pipeline.run_pipeline
```

## Local Dev (Conda)

```bash
conda env create -f environment.yml
conda activate nexen-profiler
cd user_profiler
python -m app.pipeline.run_pipeline
```

## Docker (Postgres + pgvector)

```bash
docker compose up --build
```

API endpoints:
- `GET /profile/{user_id}`
- `GET /profile/{user_id}/explain/{item_id}`

See `user_profiler/README.md` for detailed configuration.
