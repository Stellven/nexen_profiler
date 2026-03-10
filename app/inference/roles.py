from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

from app.inference.types import InferenceItem
from app.signals.types import SignalData


def _load_roles(path: Path) -> List[Dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data.get("roles", []) if data else []


def _collect_counts(signals: List[SignalData]) -> Dict[str, Dict[str, int]]:
    counts: Dict[str, Dict[str, int]] = {"action": {}, "artifact": {}, "entity": {}, "topic": {}}
    for signal in signals:
        if signal.type not in counts:
            continue
        counts[signal.type][signal.name] = counts[signal.type].get(signal.name, 0) + 1
    return counts


def _normalize_expected(expected: Dict[str, List[str]]) -> Dict[str, List[str]]:
    key_map = {
        "actions": "action",
        "artifacts": "artifact",
        "entities": "entity",
        "topics": "topic",
    }
    normalized: Dict[str, List[str]] = {}
    for key, names in expected.items():
        normalized[key_map.get(key, key)] = names
    return normalized


def _score_expected(expected: Dict[str, List[str]], counts: Dict[str, Dict[str, int]]) -> Tuple[float, Dict[str, List[str]]]:
    normalized = _normalize_expected(expected)
    total = 0
    matched = 0
    matched_by_type: Dict[str, List[str]] = {}
    for key, names in normalized.items():
        total += len(names)
        for name in names:
            if counts.get(key, {}).get(name):
                matched += 1
                matched_by_type.setdefault(key, []).append(name)
    if total == 0:
        return 0.0, {}
    return matched / total, matched_by_type


def infer_roles(
    user_id: str,
    signals: List[SignalData],
    events_by_id: Dict[str, Dict],
    roles_path: Path,
    fingerprint_days: int = 90,
) -> List[InferenceItem]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=fingerprint_days)
    recent_event_ids = {eid for eid, ev in events_by_id.items() if ev["timestamp"] >= cutoff}
    recent_signals = [s for s in signals if s.event_id in recent_event_ids]

    counts = _collect_counts(recent_signals)
    roles = _load_roles(roles_path)
    results: List[InferenceItem] = []

    total_score = 0.0
    role_scores: List[Tuple[Dict, float, Dict[str, List[str]]]] = []
    for role in roles:
        expected = role.get("expected", {})
        score, matched_by_type = _score_expected(expected, counts)
        role_scores.append((role, score, matched_by_type))
        total_score += score

    for role, score, matched_by_type in role_scores:
        probability = score / total_score if total_score > 0 else 0.0
        inference_id = hashlib.sha256(f"role:{user_id}:{role['role_id']}".encode("utf-8")).hexdigest()
        matched_names = [name for names in matched_by_type.values() for name in names]
        evidence_signal_ids = [s.signal_id for s in recent_signals if s.name in matched_names]
        evidence_event_ids = list({s.event_id for s in recent_signals if s.signal_id in evidence_signal_ids})
        description_parts = []
        for key in ("action", "artifact", "entity", "topic"):
            matched = matched_by_type.get(key, [])
            if matched:
                description_parts.append(f"{key}s: {', '.join(matched[:6])}")
        description = f"Matched expected signals for {role['role_id']}"
        if description_parts:
            description += " (" + "; ".join(description_parts) + ")"
        results.append(
            InferenceItem(
                inference_id=inference_id,
                category="role",
                label=role["role_id"],
                description=description,
                probability=probability,
                confidence=min(1.0, score + 0.2),
                time_frame={"start": cutoff.isoformat(), "end": now.isoformat(), "window_days": fingerprint_days},
                evidence_event_ids=evidence_event_ids,
                evidence_signal_ids=evidence_signal_ids,
                method={"method": "prototype_match", "version": "1.0", "ontology_path": role.get("ontology_path")},
                first_seen=cutoff,
                last_seen=now,
            )
        )

    unknown_prob = max(0.0, 1.0 - sum(item.probability or 0 for item in results))
    unknown_id = hashlib.sha256(f"role:{user_id}:unknown".encode("utf-8")).hexdigest()
    results.append(
        InferenceItem(
            inference_id=unknown_id,
            category="role",
            label="unknown",
            description="Unclassified or insufficient evidence",
            probability=unknown_prob,
            confidence=0.5,
            time_frame={"start": cutoff.isoformat(), "end": now.isoformat(), "window_days": fingerprint_days},
            evidence_event_ids=list(recent_event_ids),
            evidence_signal_ids=[s.signal_id for s in recent_signals],
            method={"method": "prototype_match", "version": "1.0"},
            first_seen=cutoff,
            last_seen=now,
        )
    )

    return results
