from __future__ import annotations

from pathlib import Path
import os

import pytest

from app.pipeline.config import PipelineConfig
from app.pipeline.run_pipeline import PipelineRunner
from app.storage.db import get_session, init_db
from app.storage.models import Event


@pytest.mark.skipif(
    not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
    reason="Gemini API key required for embeddings and LLM reasoning",
)
def test_idempotent_ingestion(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "note.md").write_text("Plan: build a parser", encoding="utf-8")

    db_path = tmp_path / "test.db"
    config = PipelineConfig(
        base_dir=data_dir,
        user_id="test",
        write_paths=[data_dir],
        read_paths=[data_dir],
        browse_path=None,
        db_url=f"sqlite:///{db_path}",
    )
    init_db(config.db_url)
    runner = PipelineRunner(config)
    runner.run()
    runner.run()

    with get_session(config.db_url) as session:
        count = session.query(Event).count()
    assert count == 1
