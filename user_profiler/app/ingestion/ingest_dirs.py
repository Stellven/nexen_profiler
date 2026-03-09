from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from app.pipeline.config import PipelineConfig


@dataclass(frozen=True)
class RawInput:
    source: str
    path: Path
    content_type: str


_IGNORE_DIRS = {".git", "user_profiler", "__pycache__", ".venv", "venv"}


def _content_type_for(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".html", ".htm"}:
        return "text/html"
    if ext == ".pdf":
        return "application/pdf"
    if ext == ".md":
        return "text/markdown"
    if ext == ".txt":
        return "text/plain"
    if ext == ".py":
        return "code/python"
    if ext == ".ipynb":
        return "application/x-ipynb"
    return "application/octet-stream"


def _scan_paths(paths: List[Path]) -> List[Path]:
    results: List[Path] = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            results.append(path)
        else:
            for p in path.rglob("*"):
                if not p.is_file():
                    continue
                if any(part in _IGNORE_DIRS for part in p.parts):
                    continue
                results.append(p)
    return results


def collect_inputs(config: PipelineConfig) -> List[RawInput]:
    items: List[RawInput] = []
    seen = set()

    for path in _scan_paths(config.write_paths):
        key = path.resolve()
        if key in seen:
            continue
        seen.add(key)
        items.append(RawInput(source="write", path=path, content_type=_content_type_for(path)))

    for path in _scan_paths(config.read_paths):
        key = path.resolve()
        if key in seen:
            continue
        seen.add(key)
        items.append(RawInput(source="read", path=path, content_type=_content_type_for(path)))

    return items
