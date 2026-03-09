from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Dict, List

from app.inference.types import InferenceItem


def infer_style(user_id: str, events_by_id: Dict[str, Dict]) -> List[InferenceItem]:
    write_events = [ev for ev in events_by_id.values() if ev["source"] == "write"]
    if not write_events:
        return []

    total_lines = 0
    bullet_lines = 0
    heading_lines = 0
    code_marks = 0
    total_chars = 0
    total_sentences = 0

    first_seen = None
    last_seen = None
    for ev in write_events:
        text = ev["content_text"]
        lines = text.splitlines()
        total_lines += len(lines)
        bullet_lines += sum(1 for line in lines if line.strip().startswith(("-", "*", "1.")))
        heading_lines += sum(1 for line in lines if line.strip().startswith("#"))
        code_marks += text.count("```") + text.count("def ") + text.count("class ")
        total_chars += len(text)
        total_sentences += max(1, text.count("."))
        ts = ev.get("timestamp")
        if ts is not None:
            first_seen = ts if first_seen is None else min(first_seen, ts)
            last_seen = ts if last_seen is None else max(last_seen, ts)

    results: List[InferenceItem] = []
    if total_lines > 0 and (bullet_lines + heading_lines) / total_lines > 0.2:
        inference_id = hashlib.sha256(f"style:{user_id}:structured".encode("utf-8")).hexdigest()
        results.append(
            InferenceItem(
                inference_id=inference_id,
                category="style",
                label="structured_notes",
                description="Writing style shows structured notes (headings/bullets)",
                probability=None,
                confidence=0.7,
                time_frame={"start": first_seen.isoformat() if first_seen else None, "end": last_seen.isoformat() if last_seen else None},
                evidence_event_ids=[ev["event_id"] for ev in write_events],
                evidence_signal_ids=[],
                method={"method": "write_heuristics", "version": "1.0"},
            )
        )
    if code_marks > 3:
        inference_id = hashlib.sha256(f"style:{user_id}:code".encode("utf-8")).hexdigest()
        results.append(
            InferenceItem(
                inference_id=inference_id,
                category="style",
                label="code_heavy",
                description="Writing style includes code snippets or code structure",
                probability=None,
                confidence=0.6,
                time_frame={"start": first_seen.isoformat() if first_seen else None, "end": last_seen.isoformat() if last_seen else None},
                evidence_event_ids=[ev["event_id"] for ev in write_events],
                evidence_signal_ids=[],
                method={"method": "write_heuristics", "version": "1.0"},
            )
        )
    avg_sentence_len = total_chars / total_sentences if total_sentences else 0
    if avg_sentence_len < 120:
        inference_id = hashlib.sha256(f"style:{user_id}:concise".encode("utf-8")).hexdigest()
        results.append(
            InferenceItem(
                inference_id=inference_id,
                category="style",
                label="concise",
                description="Writing style tends toward short to medium sentences",
                probability=None,
                confidence=0.5,
                time_frame={"start": first_seen.isoformat() if first_seen else None, "end": last_seen.isoformat() if last_seen else None},
                evidence_event_ids=[ev["event_id"] for ev in write_events],
                evidence_signal_ids=[],
                method={"method": "write_heuristics", "version": "1.0"},
            )
        )

    return results
