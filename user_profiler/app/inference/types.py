from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class InferenceItem:
    inference_id: str
    category: str
    label: str
    description: str
    probability: Optional[float]
    confidence: float
    time_frame: Dict
    evidence_event_ids: List[str]
    evidence_signal_ids: List[str]
    method: Dict
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
