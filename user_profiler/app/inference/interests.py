from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List

from app.inference.types import InferenceItem
from app.signals.types import SignalData
from urllib.parse import urlparse


def _domain(uri: str) -> str:
    try:
        return urlparse(uri).netloc or ""
    except Exception:
        return ""


def infer_interests(user_id: str, signals: List[SignalData], events_by_id: Dict[str, Dict]) -> List[InferenceItem]:
    topic_signals = [s for s in signals if s.type == "topic"]
    by_topic = defaultdict(list)
    for signal in topic_signals:
        by_topic[signal.name].append(signal)

    results: List[InferenceItem] = []
    for topic, topic_signals in by_topic.items():
        dates = set()
        event_ids = set()
        for signal in topic_signals:
            ev = events_by_id.get(signal.event_id)
            if not ev:
                continue
            dates.add(ev["timestamp"].date())
            event_ids.add(signal.event_id)
        signal_count = len(topic_signals)
        if len(dates) < 2 and len(event_ids) < 2 and signal_count < 4:
            continue
        source_counts = Counter()
        domain_counts = Counter()
        for eid in event_ids:
            ev = events_by_id.get(eid)
            if not ev:
                continue
            source_counts[ev.get("source") or "unknown"] += 1
            if ev.get("source") == "browse":
                dom = _domain(ev.get("uri") or "")
                if dom:
                    domain_counts[dom] += 1
        inference_id = hashlib.sha256(f"interest:{user_id}:{topic}".encode("utf-8")).hexdigest()
        first_seen = min(events_by_id[eid]["timestamp"] for eid in event_ids)
        last_seen = max(events_by_id[eid]["timestamp"] for eid in event_ids)
        desc_parts = [f"Repeated attention to topic '{topic}'"]
        desc_parts.append(f"{len(event_ids)} events across {len(dates) or 1} day(s)")
        if source_counts:
            top_sources = ", ".join(f"{k}:{v}" for k, v in source_counts.most_common(3))
            desc_parts.append(f"sources {top_sources}")
        if domain_counts:
            top_domains = ", ".join(f"{k}:{v}" for k, v in domain_counts.most_common(3))
            desc_parts.append(f"domains {top_domains}")
        results.append(
            InferenceItem(
                inference_id=inference_id,
                category="interest",
                label=topic,
                description="; ".join(desc_parts),
                probability=None,
                confidence=min(1.0, 0.4 + 0.1 * len(dates)),
                time_frame={"start": first_seen.isoformat(), "end": last_seen.isoformat()},
                evidence_event_ids=list(event_ids),
                evidence_signal_ids=[s.signal_id for s in topic_signals],
                method={"method": "topic_persistence", "version": "1.0"},
                first_seen=first_seen,
                last_seen=last_seen,
            )
        )
    return results
