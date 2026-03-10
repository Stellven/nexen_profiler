from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Dict, List

from app.inference.types import InferenceItem
from app.signals.types import SignalData


_PRODUCTION_ACTIONS = {"implement", "debug", "decide", "compare"}
_PROOF_ARTIFACTS = {"code", "notebook"}


def infer_specialties(user_id: str, signals: List[SignalData], events_by_id: Dict[str, Dict]) -> List[InferenceItem]:
    topic_signals = [s for s in signals if s.type == "topic"]
    action_signals = [s for s in signals if s.type == "action" and s.name in _PRODUCTION_ACTIONS]
    artifact_signals = [s for s in signals if s.type == "artifact" and s.name in _PROOF_ARTIFACTS]

    topic_events = defaultdict(set)
    for signal in topic_signals:
        topic_events[signal.name].add(signal.event_id)

    results: List[InferenceItem] = []
    for topic, event_ids in topic_events.items():
        has_action = any(s.event_id in event_ids for s in action_signals)
        has_artifact = any(s.event_id in event_ids for s in artifact_signals)
        if not (has_action and has_artifact):
            continue
        first_seen = min(events_by_id[eid]["timestamp"] for eid in event_ids)
        last_seen = max(events_by_id[eid]["timestamp"] for eid in event_ids)
        inference_id = hashlib.sha256(f"specialty:{user_id}:{topic}".encode("utf-8")).hexdigest()
        evidence_signal_ids = [s.signal_id for s in topic_signals if s.name == topic]
        evidence_signal_ids += [s.signal_id for s in action_signals if s.event_id in event_ids]
        evidence_signal_ids += [s.signal_id for s in artifact_signals if s.event_id in event_ids]
        description = f"Proof-of-work in '{topic}'"
        if has_action and has_artifact:
            description += " (actions + artifacts observed)"
        results.append(
            InferenceItem(
                inference_id=inference_id,
                category="specialty",
                label=topic,
                description=description,
                probability=None,
                confidence=0.7,
                time_frame={"start": first_seen.isoformat(), "end": last_seen.isoformat()},
                evidence_event_ids=list(event_ids),
                evidence_signal_ids=list(dict.fromkeys(evidence_signal_ids)),
                method={"method": "proof_of_work", "version": "1.0"},
                first_seen=first_seen,
                last_seen=last_seen,
            )
        )
    return results
