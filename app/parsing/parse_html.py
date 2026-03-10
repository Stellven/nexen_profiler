from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from bs4 import BeautifulSoup


@dataclass
class ParseResult:
    text: str
    title: Optional[str]
    metadata: Dict
    parse_error: Optional[str] = None


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ")
    return " ".join(text.split())


def parse_html(path: Path) -> ParseResult:
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(raw, "lxml")
        title = soup.title.string.strip() if soup.title and soup.title.string else path.stem
        text = _extract_text(raw)
        return ParseResult(text=text, title=title, metadata={"parser": "bs4"})
    except Exception as exc:
        return ParseResult(text="", title=path.stem, metadata={"parser": "bs4"}, parse_error=str(exc))
