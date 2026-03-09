from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Dict, List
from urllib.parse import urlparse

from app.inference.types import InferenceItem
from app.signals.types import SignalData


def infer_recent(
    user_id: str,
    events_by_id: Dict[str, Dict],
    signals: List[SignalData],
    generated_at: datetime,
    window_days: int = 7,
) -> List[InferenceItem]:
    cutoff = generated_at - timedelta(days=window_days)
    signals_by_event = {}
    for signal in signals:
        signals_by_event.setdefault(signal.event_id, []).append(signal.signal_id)

    results: List[InferenceItem] = []
    browse_groups: Dict[str, List[Dict]] = {}
    for event in events_by_id.values():
        if not (cutoff <= event["timestamp"] <= generated_at):
            continue
        label = event.get("title") or event.get("uri") or "activity"
        if event.get("source") == "browse":
            url = event.get("uri") or ""
            domain = urlparse(url).netloc or ""
            browse_label = domain or label
            browse_groups.setdefault(browse_label, []).append(event)
            continue
        inference_id = hashlib.sha256(f"recent:{user_id}:{event['event_id']}".encode("utf-8")).hexdigest()
        results.append(
            InferenceItem(
                inference_id=inference_id,
                category="recent_activity",
                label=label,
                description=f"Activity from {event['source']} source",
                probability=None,
                confidence=0.8,
                time_frame={"start": event["timestamp"].isoformat(), "end": event["timestamp"].isoformat()},
                evidence_event_ids=[event["event_id"]],
                evidence_signal_ids=signals_by_event.get(event["event_id"], []),
                method={"method": "recent_window", "version": "1.0"},
                first_seen=event["timestamp"],
                last_seen=event["timestamp"],
            )
        )
    for label, events in browse_groups.items():
        event_ids = [ev["event_id"] for ev in events]
        signal_ids = []
        for eid in event_ids:
            signal_ids.extend(signals_by_event.get(eid, []))
        times = [ev["timestamp"] for ev in events]
        first_seen = min(times)
        last_seen = max(times)
        inference_id = hashlib.sha256(f"recent:{user_id}:browse:{label}".encode("utf-8")).hexdigest()
        results.append(
            InferenceItem(
                inference_id=inference_id,
                category="recent_activity",
                label=label,
                description=f"Browsing activity ({len(events)} visits)",
                probability=None,
                confidence=0.8,
                time_frame={"start": first_seen.isoformat(), "end": last_seen.isoformat()},
                evidence_event_ids=event_ids,
                evidence_signal_ids=list(dict.fromkeys(signal_ids)),
                method={"method": "recent_window", "version": "1.1"},
                first_seen=first_seen,
                last_seen=last_seen,
            )
        )
    return results
