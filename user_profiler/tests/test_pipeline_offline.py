from __future__ import annotations

from pathlib import Path
import os

import pytest

from app.pipeline.config import PipelineConfig
from app.pipeline.run_pipeline import PipelineRunner


@pytest.mark.skipif(
    not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
    reason="Gemini API key required for embeddings and LLM reasoning",
)
def test_pipeline_profile(tmp_path: Path):
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
    runner = PipelineRunner(config)
    profile = runner.run()
    assert profile["profile_view"]
