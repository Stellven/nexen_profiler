from __future__ import annotations

import hashlib
import re
from typing import List, Set
from urllib.parse import urlparse

from app.signals.types import SignalData


def _domain_from_uri(uri: str) -> str:
    parsed = urlparse(uri)
    return parsed.netloc


def _python_imports(text: str) -> Set[str]:
    imports: Set[str] = set()
    for match in re.finditer(r"^\s*import\s+([A-Za-z_][\w\.]*)", text, flags=re.MULTILINE):
        imports.add(match.group(1).split(".")[0])
    for match in re.finditer(r"^\s*from\s+([A-Za-z_][\w\.]*)\s+import", text, flags=re.MULTILINE):
        imports.add(match.group(1).split(".")[0])
    return imports


def _capitalized_entities(text: str) -> Set[str]:
    entities: Set[str] = set()
    for match in re.finditer(r"\b([A-Z][a-z]{2,})\b", text):
        entities.add(match.group(1))
    return entities


def entity_signals(event_id: str, uri: str, content_text: str) -> List[SignalData]:
    signals: List[SignalData] = []
    domain = _domain_from_uri(uri)
    if domain:
        signal_id = hashlib.sha256(f"entity:{event_id}:domain:{domain}".encode("utf-8")).hexdigest()
        signals.append(
            SignalData(
                signal_id=signal_id,
                event_id=event_id,
                chunk_id=None,
                type="entity",
                name=domain,
                value={"type": "domain"},
                confidence=0.8,
                evidence_spans=[],
                computed_by={"method": "url_domain", "version": "1.0"},
            )
        )

    for imp in sorted(_python_imports(content_text)):
        signal_id = hashlib.sha256(f"entity:{event_id}:import:{imp}".encode("utf-8")).hexdigest()
        signals.append(
            SignalData(
                signal_id=signal_id,
                event_id=event_id,
                chunk_id=None,
                type="entity",
                name=imp,
                value={"type": "import"},
                confidence=0.7,
                evidence_spans=[],
                computed_by={"method": "python_imports", "version": "1.0"},
            )
        )

    for ent in sorted(_capitalized_entities(content_text))[:10]:
        signal_id = hashlib.sha256(f"entity:{event_id}:cap:{ent}".encode("utf-8")).hexdigest()
        signals.append(
            SignalData(
                signal_id=signal_id,
                event_id=event_id,
                chunk_id=None,
                type="entity",
                name=ent,
                value={"type": "capitalized"},
                confidence=0.3,
                evidence_spans=[],
                computed_by={"method": "capitalized", "version": "1.0"},
            )
        )

    return signals
