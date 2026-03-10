from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class ParseResult:
    text: str
    title: Optional[str]
    metadata: Dict
    parse_error: Optional[str] = None


def parse_text(path: Path) -> ParseResult:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        title = path.stem
        return ParseResult(text=text, title=title, metadata={})
    except Exception as exc:
        return ParseResult(text="", title=path.stem, metadata={}, parse_error=str(exc))
