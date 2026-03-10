from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Set


@dataclass
class Session:
    session_id: str
    event_ids: List[str]
    start: datetime
    end: datetime
    topics: Set[str]


def sessionize(events: List[Dict], event_topics: Dict[str, Set[str]], gap_minutes: int) -> List[Session]:
    sessions: List[Session] = []
    if not events:
        return sessions
    events_sorted = sorted(events, key=lambda e: e["timestamp"])
    current = None
    gap = timedelta(minutes=gap_minutes)
    for event in events_sorted:
        ts = event["timestamp"]
        topics = event_topics.get(event["event_id"], set())
        if current is None:
            current = Session(session_id=event["event_id"], event_ids=[event["event_id"]], start=ts, end=ts, topics=set(topics))
            continue
        if ts - current.end <= gap:
            current.event_ids.append(event["event_id"])
            current.end = ts
            current.topics.update(topics)
        else:
            sessions.append(current)
            current = Session(session_id=event["event_id"], event_ids=[event["event_id"]], start=ts, end=ts, topics=set(topics))
    if current:
        sessions.append(current)
    return sessions
