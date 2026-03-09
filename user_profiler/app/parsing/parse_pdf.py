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


def parse_pdf(path: Path) -> ParseResult:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency optional
        return ParseResult(text="", title=path.stem, metadata={}, parse_error=f"pypdf unavailable: {exc}")
    try:
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        text = "\n\n".join(pages)
        return ParseResult(text=text, title=path.stem, metadata={"pages": len(reader.pages)})
    except Exception as exc:
        return ParseResult(text="", title=path.stem, metadata={}, parse_error=str(exc))
