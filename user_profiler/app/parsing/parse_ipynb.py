from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class ParseResult:
    text: str
    title: Optional[str]
    metadata: Dict
    parse_error: Optional[str] = None


def parse_ipynb(path: Path) -> ParseResult:
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        data = json.loads(raw)
        cells = []
        for cell in data.get("cells", []):
            if isinstance(cell, dict):
                source = cell.get("source", [])
                if isinstance(source, list):
                    cells.append("".join(source))
                elif isinstance(source, str):
                    cells.append(source)
        text = "\n\n".join(cells)
        return ParseResult(text=text, title=path.stem, metadata={"cell_count": len(cells)})
    except Exception as exc:
        return ParseResult(text="", title=path.stem, metadata={}, parse_error=str(exc))
