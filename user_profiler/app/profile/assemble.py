from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Dict, List

from app.inference.types import InferenceItem
from app.profile.schema_v1_1 import ProfileJSON
from app.signals.types import SignalData


def attach_default_signals(inferences: List[InferenceItem], signals: List[SignalData]) -> None:
    by_event = {}
    for signal in signals:
        by_event.setdefault(signal.event_id, []).append(signal.signal_id)
    for inference in inferences:
        if inference.evidence_signal_ids:
            continue
        collected = []
        for event_id in inference.evidence_event_ids:
            collected.extend(by_event.get(event_id, []))
        inference.evidence_signal_ids = list(dict.fromkeys(collected))


def filter_inferences(inferences: List[InferenceItem]) -> List[InferenceItem]:
    filtered = []
    for inference in inferences:
        if not inference.evidence_event_ids:
            continue
        if not inference.evidence_signal_ids:
            continue
        filtered.append(inference)
    return filtered


def _profile_item(inference: InferenceItem) -> Dict:
    return {
        "item_id": inference.inference_id,
        "label": inference.label,
        "description": inference.description,
        "time_frame": inference.time_frame,
        "confidence": inference.confidence,
        "evidence": {
            "event_ids": inference.evidence_event_ids,
            "signal_ids": inference.evidence_signal_ids,
        },
    }


def assemble_profile(
    generated_at: datetime,
    events: List[Dict],
    signals: List[SignalData],
    projects: List[Dict],
    inferences: List[InferenceItem],
) -> ProfileJSON:
    attach_default_signals(inferences, signals)
    inferences = filter_inferences(inferences)

    action_counts = Counter(s.name for s in signals if s.type == "action")
    artifact_counts = Counter(s.name for s in signals if s.type == "artifact")
    entity_counts = Counter(s.name for s in signals if s.type == "entity")
    topic_counts = Counter(s.name for s in signals if s.type == "topic")

    observed_facts = {
        "event_count": len(events),
        "actions": dict(action_counts),
        "artifacts": dict(artifact_counts),
        "entities": dict(entity_counts),
        "topics": dict(topic_counts),
    }

    role_distribution = [inf for inf in inferences if inf.category == "role"]
    user_state = {
        "projects": projects,
        "role_distribution": [
            {"label": r.label, "probability": r.probability, "confidence": r.confidence}
            for r in role_distribution
        ],
        "expertise_map": [inf.label for inf in inferences if inf.category == "specialty"],
        "preferences": [inf.label for inf in inferences if inf.category == "style"],
    }

    profile_view = {
        "roles": [_profile_item(inf) for inf in inferences if inf.category == "role"],
        "interests": [_profile_item(inf) for inf in inferences if inf.category == "interest"],
        "specialties": [_profile_item(inf) for inf in inferences if inf.category == "specialty"],
        "style": [_profile_item(inf) for inf in inferences if inf.category == "style"],
        "recent_activities": [_profile_item(inf) for inf in inferences if inf.category == "recent_activity"],
    }

    capability_pack = {
        "skills": [
            {
                "label": inf.label,
                "description": inf.description,
                "confidence": inf.confidence,
            }
            for inf in inferences
            if inf.category in {"role", "specialty"}
        ],
        "generated_at": generated_at.isoformat(),
    }

    explainability = {
        "items": len(inferences),
        "method_version": "v1.1",
    }

    return ProfileJSON(
        observed_facts=observed_facts,
        user_state=user_state,
        profile_view=profile_view,
        capability_pack=capability_pack,
        explainability=explainability,
    )
