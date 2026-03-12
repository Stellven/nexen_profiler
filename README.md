# Nexen Profiler

Nexen Profiler is a Python-based profiling pipeline that turns a user's local activity trail into a structured portrait. It ingests files the user wrote, files the user read, and optional browser history, extracts evidence-backed signals, groups work into projects, and produces both a stored JSON profile and a human-readable Markdown summary.

The repository ships with a demo dataset in [`data/`](/home/howard_kao/projects/nexen_profiler/data), so other users can run the pipeline without first preparing their own corpus.

## What It Does

Given a directory of user activity, the pipeline:

1. Ingests `write/`, `read/`, and optional `browse/history.csv` sources.
2. Parses Markdown, plain text, Python, Jupyter notebooks, HTML, and PDF files.
3. Normalizes each artifact into timestamped events.
4. Chunks content and generates embeddings.
5. Extracts signals such as topics, actions, entities, and artifact types.
6. Clusters related sessions into projects and infers project intent/status.
7. Uses Gemini-based reasoning to infer higher-level profile categories such as roles, interests, specialties, style, and recent activities.
8. Stores everything in a database and writes a timestamped Markdown portrait.

The API layer exposes the latest stored profile and an explanation endpoint for individual inference items.

## Main Technology Choices

- Python 3.11: core implementation language for ingestion, parsing, inference, storage, and API.
- FastAPI + Uvicorn: lightweight HTTP API for serving stored profiles.
- SQLAlchemy 2.x: persistence layer across SQLite and PostgreSQL.
- PostgreSQL + pgvector: production-oriented vector storage path for embeddings when running with Docker.
- SQLite: simplest local development default.
- Google Gemini via `google-genai`: required for both embeddings and LLM reasoning in the current implementation.
- BeautifulSoup + lxml + pypdf: local parsing of HTML and PDF inputs.

## Repository Layout

- [`app/`](/home/howard_kao/projects/nexen_profiler/app): ingestion, parsing, embedding, inference, profile assembly, and API code.
- [`data/`](/home/howard_kao/projects/nexen_profiler/data): demo dataset.
- [`docker/`](/home/howard_kao/projects/nexen_profiler/docker): API and worker container definitions.
- [`prototypes/`](/home/howard_kao/projects/nexen_profiler/prototypes): role taxonomy/prototype assets used by the pipeline.
- [`tests/`](/home/howard_kao/projects/nexen_profiler/tests): focused tests around pipeline behavior and evidence constraints.
- [`ExampleUserProfile.md`](/home/howard_kao/projects/nexen_profiler/ExampleUserProfile.md): example of the generated portrait format.

## Input Data Format

By default the pipeline looks under `data/` if that directory exists.

- `data/write/`: artifacts created by the user, such as notes or code.
- `data/read/`: documents consumed by the user, such as PDFs or saved webpages.
- `data/browse/history.csv`: optional browser history export.

If `write/` and `read/` do not exist, the pipeline falls back to treating the configured `DATA_DIR` as a flat source directory.

Supported file types in the current code:

- `.md`
- `.txt`
- `.py`
- `.ipynb`
- `.html` / `.htm`
- `.pdf`

## Running Locally

### Prerequisites

- Python 3.11
- A Gemini API key exposed as `GEMINI_API_KEY` or `GOOGLE_API_KEY`

Important: parsing is local, but a full pipeline run is not fully offline right now. Embeddings and LLM reasoning both require Gemini access.

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
set -a
source .env
set +a
```

You can use the provided environment template in [`.env.example`](/home/howard_kao/projects/nexen_profiler/.env.example) and adjust values as needed.

### Run The Pipeline

From the repo root:

```bash
python -m app.pipeline.run_pipeline
```

With the bundled demo data, this will:

- create a local SQLite database at `user_profiler.db`
- ingest the sample files under [`data/`](/home/howard_kao/projects/nexen_profiler/data)
- store events, chunks, embeddings, signals, projects, and profile records
- write a timestamped Markdown profile such as `profile_20260312_153000.md`

### Serve The API Locally

After generating a profile, start the API:

```bash
uvicorn app.api.main:app --reload
```

The API is then available at `http://127.0.0.1:8000`.

Useful endpoints:

- `GET /profile/default_user`
- `GET /profile/default_user/explain/<inference_id>`

## Running With Docker

The repository includes a three-service Docker Compose setup:

- `postgres`: PostgreSQL with `pgvector`
- `worker`: runs the profiling pipeline
- `api`: serves the stored profile over FastAPI

Start it with:

```bash
docker compose up --build
```

The API will be exposed at `http://localhost:8000`.

Notes for Docker users:

- The compose file mounts the repository into the containers and points `DATA_DIR` at `/data/data`, which maps to the repo's local [`data/`](/home/howard_kao/projects/nexen_profiler/data) folder.
- The worker uses PostgreSQL instead of SQLite.
- Gemini credentials still need to be available inside the containers. The current compose file does not inject `GEMINI_API_KEY` automatically, so you will need to provide it when running containers or extend [`docker-compose.yml`](/home/howard_kao/projects/nexen_profiler/docker-compose.yml) to pass it through.

## Configuration

Environment variables supported by the current code:

- `DATA_DIR`: base directory holding `write/`, `read/`, and optional `browse/history.csv`. Defaults to `data/` if present, otherwise the repo root.
- `DB_URL`: SQLAlchemy database URL. Defaults to `sqlite:///user_profiler.db`.
- `USER_ID`: profile key. Defaults to `default_user`.
- `EMBEDDING_DIM`: embedding vector size in storage. Defaults to `3072`.
- `GEMINI_MODEL`: Gemini model for reasoning. If unset and the process is interactive, the pipeline prompts for one; otherwise it defaults to `gemini-2.5-flash`.
- `GEMINI_EMBED_MODEL`: embedding model name. Defaults to `gemini-embedding-001`.
- `GEMINI_EMBED_BATCH`: embedding batch size. Defaults to `100`.
- `PROFILE_LANG`: output language for the portrait text. Defaults to `zh`.
- `PROFILE_MD_PATH`: output Markdown path. If it points to a directory, the pipeline creates a timestamped file inside it.
- `ROLES_PATH`: optional override for the roles prototype YAML file.
- `NO_PROGRESS`: set to `1`, `true`, `yes`, or `y` to disable console progress output.

Example local run with explicit settings:

```bash
set -a
source .env
set +a
python -m app.pipeline.run_pipeline
```

## Testing

Run the test suite with:

```bash
pytest
```

Current test coverage focuses on:

- idempotent ingestion
- recent-activity windowing
- evidence requirements for inferences
- end-to-end pipeline execution when Gemini credentials are available

Tests that require Gemini are skipped if no API key is set.

## Outputs

The main persisted objects are:

- `events`: normalized source artifacts
- `chunks`: chunked event text spans
- `embeddings`: vectorized chunks
- `signals`: extracted topics, actions, entities, and artifact labels
- `projects`: clustered sessions with inferred intent/status
- `inferences`: evidence-linked higher-level profile claims
- `profiles`: assembled JSON portraits

You can inspect a sample portrait shape in [`ExampleUserProfile.md`](/home/howard_kao/projects/nexen_profiler/ExampleUserProfile.md).

## Current Constraints

- Gemini embeddings and Gemini reasoning are both required for a full run.
- Browser history input must be a CSV with recognizable timestamp/date-time columns.
- The API serves whatever profile is already stored; it does not trigger ingestion on request.
- The README documents the code as it exists now. If you want a truly offline path, the embedding and reasoning layers would need alternative local backends.
