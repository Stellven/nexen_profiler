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


def parse_code(path: Path) -> ParseResult:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return ParseResult(text=text, title=path.stem, metadata={"language": path.suffix.lstrip(".")})
    except Exception as exc:
        return ParseResult(text="", title=path.stem, metadata={}, parse_error=str(exc))
