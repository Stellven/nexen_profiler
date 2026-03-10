from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from app.signals.types import SignalData


_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "will", "are", "was", "were", "your", "you",
    "about", "into", "over", "under", "into", "out", "not", "but", "what", "when", "where", "which", "their",
}


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _keywords(text: str, limit: int = 2) -> str:
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    freq: Dict[str, int] = {}
    for word in words:
        if word in _STOPWORDS:
            continue
        freq[word] = freq.get(word, 0) + 1
    sorted_words = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
    top = [w for w, _ in sorted_words[:limit]]
    return " ".join(top) if top else "misc"


@dataclass
class Topic:
    label: str
    centroid: List[float]
    count: int = 0


@dataclass
class TopicAssigner:
    threshold: float
    topics: List[Topic] = field(default_factory=list)

    def assign(self, embedding: List[float], chunk_text: str) -> Topic:
        if not self.topics:
            label = _keywords(chunk_text)
            topic = Topic(label=label, centroid=embedding, count=1)
            self.topics.append(topic)
            return topic
        best_idx = -1
        best_score = -1.0
        for idx, topic in enumerate(self.topics):
            score = _cosine(topic.centroid, embedding)
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_score >= self.threshold:
            topic = self.topics[best_idx]
            # update centroid
            topic.count += 1
            topic.centroid = [
                (topic.centroid[i] * (topic.count - 1) + embedding[i]) / topic.count
                for i in range(len(embedding))
            ]
            return topic
        label = _keywords(chunk_text)
        topic = Topic(label=label, centroid=embedding, count=1)
        self.topics.append(topic)
        return topic


def topic_signal(event_id: str, chunk_id: str, topic_label: str) -> SignalData:
    signal_id = hashlib.sha256(f"topic:{chunk_id}:{topic_label}".encode("utf-8")).hexdigest()
    return SignalData(
        signal_id=signal_id,
        event_id=event_id,
        chunk_id=chunk_id,
        type="topic",
        name=topic_label,
        value={},
        confidence=0.6,
        evidence_spans=[],
        computed_by={"method": "embedding_topic", "version": "1.0"},
    )
