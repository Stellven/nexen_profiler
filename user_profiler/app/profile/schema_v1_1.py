from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ProfileViewItem:
    item_id: str
    label: str
    description: str
    time_frame: Dict[str, Any]
    confidence: float
    evidence: Dict[str, Any]


@dataclass
class ProfileJSON:
    observed_facts: Dict[str, Any]
    user_state: Dict[str, Any]
    profile_view: Dict[str, List[Dict[str, Any]]]
    capability_pack: Dict[str, Any]
    explainability: Dict[str, Any]
