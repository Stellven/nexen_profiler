from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class SignalData:
    signal_id: str
    event_id: str
    chunk_id: Optional[str]
    type: str
    name: str
    value: Dict
    confidence: float
    evidence_spans: List[Dict]
    computed_by: Dict
