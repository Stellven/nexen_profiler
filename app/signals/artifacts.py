from __future__ import annotations

import hashlib
from typing import List

from app.signals.types import SignalData


_ARTIFACT_MAP = {
    "text/markdown": ("note", {"format": "markdown"}),
    "text/plain": ("note", {"format": "plain"}),
    "code/python": ("code", {"language": "python"}),
    "application/x-ipynb": ("notebook", {}),
    "text/html": ("webpage", {}),
    "application/pdf": ("pdf", {}),
    "text/url": ("url", {}),
}


def artifact_signals(event_id: str, content_type: str) -> List[SignalData]:
    if content_type not in _ARTIFACT_MAP:
        return []
    name, value = _ARTIFACT_MAP[content_type]
    signal_id = hashlib.sha256(f"artifact:{event_id}:{name}".encode("utf-8")).hexdigest()
    return [
        SignalData(
            signal_id=signal_id,
            event_id=event_id,
            chunk_id=None,
            type="artifact",
            name=name,
            value=value,
            confidence=0.9,
            evidence_spans=[],
            computed_by={"method": "artifact_map", "version": "1.0"},
        )
    ]
