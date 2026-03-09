from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Tuple

from app.signals.types import SignalData


_ACTION_RULES: Dict[str, List[str]] = {
    "debug": [r"\bdebug\b", r"\berror\b", r"\bfix\b", r"\bissue\b"],
    "compare": [r"\bcompare\b", r"\bversus\b", r"\bvs\.?\b"],
    "summarize": [r"\bsummar(y|ize)\b", r"\bsummary\b"],
    "plan": [r"\bplan\b", r"\broadmap\b", r"\bnext steps\b"],
    "monitor": [r"\bmonitor\b", r"\btrack\b", r"\bwatch\b"],
    "implement": [r"\bimplement\b", r"\bbuild\b", r"\bprototype\b", r"\bcode\b"],
    "decide": [r"\bdecide\b", r"\bdecision\b", r"\bchoose\b", r"\bevaluate\b"],
    "learn": [r"\blearn\b", r"\bstudy\b", r"\bnotes\b", r"\breading\b"],
    "communicate": [r"\bshare\b", r"\bpresent\b", r"\breport\b", r"\bwrite\b"],
}


def _find_spans(text: str, patterns: List[str]) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            spans.append((match.start(), match.end()))
    return spans


def action_signals(event_id: str, chunk_id: str, chunk_text: str) -> List[SignalData]:
    signals: List[SignalData] = []
    for label, patterns in _ACTION_RULES.items():
        spans = _find_spans(chunk_text, patterns)
        if not spans:
            continue
        evidence = [{"start": s, "end": e} for s, e in spans[:5]]
        signal_id = hashlib.sha256(f"action:{chunk_id}:{label}".encode("utf-8")).hexdigest()
        signals.append(
            SignalData(
                signal_id=signal_id,
                event_id=event_id,
                chunk_id=chunk_id,
                type="action",
                name=label,
                value={},
                confidence=min(1.0, 0.4 + 0.1 * len(spans)),
                evidence_spans=evidence,
                computed_by={"method": "rules", "version": "1.0"},
            )
        )
    return signals
