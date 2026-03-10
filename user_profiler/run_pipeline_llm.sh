#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export PYTHONPATH="$SCRIPT_DIR"
export EMBEDDING_DIM="${EMBEDDING_DIM:-3072}"
export PROFILE_LANG="${PROFILE_LANG:-zh}"
export ACTION_SIGNAL_MODE="${ACTION_SIGNAL_MODE:-llm}"
export INTENT_MODE="${INTENT_MODE:-llm}"

cd "$SCRIPT_DIR"
python -m app.pipeline.run_pipeline
