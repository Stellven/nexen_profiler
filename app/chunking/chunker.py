from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List


@dataclass
class ChunkData:
    chunk_id: str
    event_id: str
    start_offset: int
    end_offset: int
    span_hash: str
    chunk_text: str


def _hash_span(text: str, start: int, end: int) -> str:
    base = f"{start}:{end}:{text}"
    return hashlib.sha256(base.encode("utf-8", errors="ignore")).hexdigest()


def chunk_text(event_id: str, text: str, max_chars: int = 1000, overlap: int = 200) -> List[ChunkData]:
    if not text:
        return []
    chunks: List[ChunkData] = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(text_len, start + max_chars)
        chunk = text[start:end]
        span_hash = _hash_span(chunk, start, end)
        chunk_id = hashlib.sha256(f"{event_id}:{span_hash}".encode("utf-8")).hexdigest()
        chunks.append(
            ChunkData(
                chunk_id=chunk_id,
                event_id=event_id,
                start_offset=start,
                end_offset=end,
                span_hash=span_hash,
                chunk_text=chunk,
            )
        )
        if end == text_len:
            break
        start = max(0, end - overlap)
    return chunks
