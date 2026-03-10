from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Tuple

from app.signals.types import SignalData


_ACTION_RULES: Dict[str, List[str]] = {
    "learn": [
        r"\blearn\b",
        r"\bstudy\b",
        r"\bnotes\b",
        r"\breading\b",
        r"\bread\b",
        r"\bwatch(ing)?\b",
        r"\blisten(ing)?\b",
        r"\btutorial\b",
        r"\bguide\b",
        r"\blesson\b",
        r"\bcourse\b",
    ],
    "summarize": [
        r"\bsummar(y|ize)\b",
        r"\bsummary\b",
        r"\brecap\b",
        r"\boverview\b",
        r"\btakeaways?\b",
    ],
    "research": [
        r"\bresearch\b",
        r"\binvestigate\b",
        r"\bsurvey\b",
        r"\breview\b",
        r"\bexplore\b",
        r"\bliterature\b",
    ],
    "analyze": [
        r"\banaly(sis|ze)\b",
        r"\bassess\b",
        r"\bmeasure\b",
        r"\bquantif(y|ication)\b",
        r"\bmodel\b",
    ],
    "compare": [
        r"\bcompare\b",
        r"\bversus\b",
        r"\bvs\.?\b",
        r"\btrade-?off\b",
        r"\bpros and cons\b",
    ],
    "decide": [
        r"\bdecide\b",
        r"\bdecision\b",
        r"\bchoose\b",
        r"\bselect\b",
        r"\bpick\b",
        r"\bevaluate\b",
    ],
    "plan": [
        r"\bplan\b",
        r"\broadmap\b",
        r"\bnext steps\b",
        r"\bschedule\b",
        r"\bitinerary\b",
        r"\bagenda\b",
        r"\bchecklist\b",
        r"\bto-?do\b",
    ],
    "organize": [
        r"\borgani[sz]e\b",
        r"\bsort\b",
        r"\bcategor(y|ize)\b",
        r"\blabel\b",
        r"\btag\b",
        r"\bclean\b",
        r"\btidy\b",
    ],
    "monitor": [
        r"\bmonitor\b",
        r"\btrack\b",
        r"\blog\b",
        r"\bwatchlist\b",
    ],
    "maintain": [
        r"\bmaintain\b",
        r"\bfix\b",
        r"\brepair\b",
        r"\bupdate\b",
        r"\bimprove\b",
        r"\boptimi[sz]e\b",
        r"\brefactor\b",
    ],
    "implement": [
        r"\bimplement\b",
        r"\bbuild\b",
        r"\bprototype\b",
        r"\bcode\b",
    ],
    "create": [
        r"\bcreate\b",
        r"\bdesign\b",
        r"\bdraft\b",
        r"\bcompose\b",
        r"\bsketch\b",
        r"\bcook\b",
        r"\bbake\b",
    ],
    "practice": [
        r"\bpractice\b",
        r"\btrain\b",
        r"\bexercise\b",
        r"\bworkout\b",
        r"\brehearse\b",
    ],
    "communicate": [
        r"\bshare\b",
        r"\bpresent\b",
        r"\breport\b",
        r"\bmessage\b",
        r"\bemail\b",
        r"\bcall\b",
        r"\bmeeting\b",
        r"\bdiscuss\b",
        r"\bpost\b",
        r"\bpublish\b",
    ],
    "collaborate": [
        r"\bcollaborate\b",
        r"\bcoordinate\b",
        r"\bsync\b",
        r"\balign\b",
    ],
    "debug": [
        r"\bdebug\b",
        r"\berror\b",
        r"\bissue\b",
    ],
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
