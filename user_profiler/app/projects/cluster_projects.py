from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import List, Set

from app.projects.sessionize import Session


@dataclass
class ProjectData:
    project_id: str
    title: str
    intent: str
    status: str
    first_seen: datetime
    last_seen: datetime
    confidence: float
    topics: Set[str]
    entities: Set[str]
    event_ids: List[str]


def _overlap(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster_sessions(sessions: List[Session], session_entities: List[Set[str]]) -> List[ProjectData]:
    projects: List[ProjectData] = []
    for session, entities in zip(sessions, session_entities):
        matched = None
        for project in projects:
            if _overlap(project.topics, session.topics) >= 0.3:
                matched = project
                break
        if matched is None:
            project_id = hashlib.sha256(f"project:{session.session_id}".encode("utf-8")).hexdigest()
            projects.append(
                ProjectData(
                    project_id=project_id,
                    title=" / ".join(sorted(session.topics)) or "untitled",
                    intent="unknown",
                    status="active",
                    first_seen=session.start,
                    last_seen=session.end,
                    confidence=0.4,
                    topics=set(session.topics),
                    entities=set(entities),
                    event_ids=list(session.event_ids),
                )
            )
        else:
            matched.last_seen = max(matched.last_seen, session.end)
            matched.first_seen = min(matched.first_seen, session.start)
            matched.topics.update(session.topics)
            matched.entities.update(entities)
            matched.event_ids.extend(session.event_ids)
    return projects
