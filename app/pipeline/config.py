from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class PipelineConfig:
    base_dir: Path
    user_id: str
    write_paths: List[Path]
    read_paths: List[Path]
    browse_path: Optional[Path]
    db_url: str
    embedding_dim: int = 768
    profile_language: str = "en"
    recent_days: int = 7
    session_gap_minutes: int = 120
    topic_similarity_threshold: float = 0.78
    fingerprint_days: int = 90


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def default_config(base_dir: Path) -> PipelineConfig:
    data_dir_env = os.getenv("DATA_DIR")
    if data_dir_env:
        data_dir = Path(data_dir_env)
    else:
        data_dir = base_dir
        if (data_dir / "data").exists():
            data_dir = data_dir / "data"
    write_dir = data_dir / "write"
    read_dir = data_dir / "read"
    write_paths = [write_dir] if write_dir.exists() else [data_dir]
    read_paths = [read_dir] if read_dir.exists() else [data_dir]
    browse_path = data_dir / "browse" / "history.csv" if (data_dir / "browse" / "history.csv").exists() else None
    if browse_path is None and (data_dir / "history.csv").exists():
        browse_path = data_dir / "history.csv"
    return PipelineConfig(
        base_dir=data_dir,
        user_id=os.getenv("USER_ID", "default_user"),
        write_paths=write_paths,
        read_paths=read_paths,
        browse_path=browse_path,
        db_url=os.getenv("DB_URL", "sqlite:///user_profiler.db"),
        embedding_dim=_env_int("EMBEDDING_DIM", 768),
        profile_language=os.getenv("PROFILE_LANG", "zh"),
    )
