from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

from app.inference.types import InferenceItem
from app.llm.gemini_client import GeminiClient, select_gemini_model
from app.signals.types import SignalData


def _top_counts(items: List[str], limit: int = 20) -> List[Dict[str, int]]:
    counts = Counter(items)
    return [{"label": k, "count": v} for k, v in counts.most_common(limit)]


def _signals_by_event(signals: List[SignalData]) -> Dict[str, List[SignalData]]:
    by_event: Dict[str, List[SignalData]] = defaultdict(list)
    for s in signals:
        by_event[s.event_id].append(s)
    return by_event


def _event_label(ev: Dict) -> str:
    title = (ev.get("title") or "").strip()
    uri = ev.get("uri") or ""
    if ev.get("source") == "browse":
        domain = urlparse(uri).netloc
        return title or domain or uri or "browse"
    try:
        stem = Path(uri).stem if uri else ""
    except Exception:
        stem = ""
    return title or stem or uri or "event"


def _snippet(text: str, limit: int = 240) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "..."


def _select_events(events_by_id: Dict[str, Dict], event_ids: List[str], total_limit: int = 80, per_source: int = 25) -> List[Dict]:
    grouped: Dict[str, List[Dict]] = defaultdict(list)
    for eid in event_ids:
        ev = events_by_id.get(eid)
        if not ev:
            continue
        grouped[ev.get("source") or "unknown"].append(ev)
    selected: List[Dict] = []
    for source, events in grouped.items():
        events.sort(key=lambda e: e.get("timestamp"), reverse=True)
        selected.extend(events[:per_source])
    selected.sort(key=lambda e: e.get("timestamp"), reverse=True)
    return selected[:total_limit]


class LLMReasoner:
    def __init__(self, roles_path: Path, model: str | None = None, api_key: str | None = None) -> None:
        self.roles_path = roles_path
        self.model = model or select_gemini_model()
        self.client = GeminiClient(model=self.model, api_key=api_key)

    def infer(
        self,
        user_id: str,
        events_by_id: Dict[str, Dict],
        signals: List[SignalData],
        fingerprint_days: int = 90,
        recent_days: int = 7,
        language: str = "en",
    ) -> List[InferenceItem]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=fingerprint_days)
        recent_cutoff = now - timedelta(days=recent_days)

        recent_event_ids = [eid for eid, ev in events_by_id.items() if ev["timestamp"] >= cutoff]
        recent_signals = [s for s in signals if s.event_id in set(recent_event_ids)]
        by_event = _signals_by_event(recent_signals)

        selected_events = _select_events(events_by_id, recent_event_ids)
        recent_event_ids_window = [eid for eid, ev in events_by_id.items() if ev["timestamp"] >= recent_cutoff]
        recent_events = _select_events(events_by_id, recent_event_ids_window, total_limit=40, per_source=15)
        selected_event_ids = {ev["event_id"] for ev in selected_events}

        event_summaries: List[Dict] = []
        ref_to_id: Dict[str, str] = {}
        for idx, ev in enumerate(selected_events, 1):
            ev_signals = by_event.get(ev["event_id"], [])
            topics = sorted({s.name for s in ev_signals if s.type == "topic"})[:6]
            actions = sorted({s.name for s in ev_signals if s.type == "action"})[:6]
            artifacts = sorted({s.name for s in ev_signals if s.type == "artifact"})[:4]
            entities = []
            for s in ev_signals:
                if s.type != "entity":
                    continue
                ent_type = s.value.get("type") if isinstance(s.value, dict) else None
                if ent_type in {"domain", "import"}:
                    entities.append(s.name)
            entities = sorted(set(entities))[:6]
            uri = ev.get("uri") or ""
            ref = f"E{idx}"
            ref_to_id[ref] = ev["event_id"]
            event_summaries.append(
                {
                    "ref": ref,
                    "event_id": ev["event_id"],
                    "label": _event_label(ev),
                    "source": ev.get("source"),
                    "date": ev.get("timestamp").date().isoformat() if ev.get("timestamp") else None,
                    "domain": urlparse(uri).netloc or None,
                    "topics": topics,
                    "actions": actions,
                    "artifacts": artifacts,
                    "entities": entities,
                    "snippet": _snippet(ev.get("content_text") or "") if ev.get("source") != "browse" else "",
                }
            )

        recent_event_summaries: List[Dict] = []
        recent_ref_to_id: Dict[str, str] = {}
        for idx, ev in enumerate(recent_events, 1):
            ref = f"R{idx}"
            recent_ref_to_id[ref] = ev["event_id"]
            uri = ev.get("uri") or ""
            recent_event_summaries.append(
                {
                    "ref": ref,
                    "event_id": ev["event_id"],
                    "label": _event_label(ev),
                    "source": ev.get("source"),
                    "date": ev.get("timestamp").date().isoformat() if ev.get("timestamp") else None,
                    "domain": urlparse(uri).netloc or None,
                    "snippet": _snippet(ev.get("content_text") or "") if ev.get("source") != "browse" else "",
                }
            )

        topic_events: Dict[str, List[str]] = defaultdict(list)
        for s in recent_signals:
            if s.type == "topic" and s.event_id in selected_event_ids:
                topic_events[s.name].append(s.event_id)

        topic_bundles: List[Dict[str, object]] = []
        for topic, ev_ids in topic_events.items():
            if not ev_ids:
                continue
            source_counts = Counter()
            domain_counts = Counter()
            for eid in set(ev_ids):
                ev = events_by_id.get(eid)
                if not ev:
                    continue
                source_counts[ev.get("source") or "unknown"] += 1
                if ev.get("source") == "browse":
                    dom = urlparse(ev.get("uri") or "").netloc
                    if dom:
                        domain_counts[dom] += 1
            topic_bundles.append(
                {
                    "topic": topic,
                    "event_count": len(set(ev_ids)),
                    "event_ids": list(dict.fromkeys(ev_ids))[:6],
                    "top_sources": [f"{k}:{v}" for k, v in source_counts.most_common(3)],
                    "top_domains": [f"{k}:{v}" for k, v in domain_counts.most_common(3)],
                }
            )
        topic_bundles.sort(key=lambda t: t.get("event_count", 0), reverse=True)
        topic_bundles = topic_bundles[:30]

        actions = [s.name for s in recent_signals if s.type == "action"]
        artifacts = [s.name for s in recent_signals if s.type == "artifact"]
        domains = []
        for s in recent_signals:
            if s.type == "entity":
                ent_type = s.value.get("type") if isinstance(s.value, dict) else None
                if ent_type == "domain":
                    domains.append(s.name)

        prompt = _build_prompt(
            event_summaries=event_summaries,
            recent_event_summaries=recent_event_summaries,
            topic_bundles=topic_bundles,
            action_counts=_top_counts(actions, 15),
            artifact_counts=_top_counts(artifacts, 10),
            domain_counts=_top_counts(domains, 15),
            recent_days=recent_days,
            language=language,
        )
        result = self.client.generate_json(prompt)

        def time_frame(event_ids: List[str]) -> Dict[str, str]:
            if not event_ids:
                return {"start": cutoff.isoformat(), "end": now.isoformat()}
            times = [events_by_id[eid]["timestamp"] for eid in event_ids if eid in events_by_id]
            if not times:
                return {"start": cutoff.isoformat(), "end": now.isoformat()}
            return {"start": min(times).isoformat(), "end": max(times).isoformat()}

        def _coerce_items(key: str) -> List[Dict]:
            items = result.get(key, [])
            if not isinstance(items, list):
                return []
            return [i for i in items if isinstance(i, dict)]

        def _build_items(key: str, category: str) -> List[InferenceItem]:
            items = []
            for item in _coerce_items(key):
                label = (item.get("label") or "").strip()
                if not label:
                    continue
                evidence_event_ids = []
                raw_ids = item.get("evidence_event_ids", [])
                if isinstance(raw_ids, list):
                    evidence_event_ids.extend(
                        [eid for eid in raw_ids if isinstance(eid, str) and eid in selected_event_ids]
                    )
                raw_refs = item.get("evidence_event_refs", [])
                if isinstance(raw_refs, list):
                    for ref in raw_refs:
                        if not isinstance(ref, str):
                            continue
                        mapped = ref_to_id.get(ref)
                        if mapped and mapped in selected_event_ids:
                            evidence_event_ids.append(mapped)
                        mapped_recent = recent_ref_to_id.get(ref)
                        if mapped_recent:
                            evidence_event_ids.append(mapped_recent)
                evidence_event_ids = list(dict.fromkeys(evidence_event_ids))
                if not evidence_event_ids:
                    continue
                confidence = max(0.0, min(1.0, float(item.get("confidence") or 0.6)))
                tf = item.get("time_frame")
                if not isinstance(tf, dict) or not tf.get("start") or not tf.get("end"):
                    tf = time_frame(evidence_event_ids)
                inference_id = hashlib.sha256(f"{category}:{user_id}:{label}".encode("utf-8")).hexdigest()
                items.append(
                    InferenceItem(
                        inference_id=inference_id,
                        category=category,
                        label=label,
                        description=item.get("description") or f"{category} inferred from evidence",
                        probability=None,
                        confidence=confidence,
                        time_frame=tf,
                        evidence_event_ids=list(dict.fromkeys(evidence_event_ids)),
                        evidence_signal_ids=[],
                        method={"method": "llm_reasoner_open", "model": self.model, "version": "2.0"},
                        first_seen=cutoff,
                        last_seen=now,
                    )
                )
            return items

        inferences: List[InferenceItem] = []
        inferences.extend(_build_items("roles", "role"))
        inferences.extend(_build_items("interests", "interest"))
        inferences.extend(_build_items("specialties", "specialty"))
        inferences.extend(_build_items("style", "style"))
        inferences.extend(_build_items("recent_activities", "recent_activity"))
        return inferences


def _build_prompt(
    event_summaries: List[Dict],
    recent_event_summaries: List[Dict],
    topic_bundles: List[Dict],
    action_counts: List[Dict[str, int]],
    artifact_counts: List[Dict[str, int]],
    domain_counts: List[Dict[str, int]],
    recent_days: int,
    language: str,
) -> str:
    lang = (language or "en").lower()
    if lang.startswith("zh"):
        lang_instruction = "Write labels and descriptions in Simplified Chinese."
    else:
        lang_instruction = "Write labels and descriptions in English."
    return (
        "You are a profiling system. Use ONLY the provided evidence.\n"
        "Do not infer sensitive traits (race, health, religion, politics, sexuality, etc.).\n"
        f"{lang_instruction}\n"
        "Return JSON with keys: roles, interests, specialties, style, recent_activities.\n"
        "Each item must include: label, description, confidence (0-1), and evidence.\n"
        "For evidence, provide either evidence_event_ids (event_id strings) or evidence_event_refs (short refs like E1).\n"
        "Optional: time_frame {start, end} as ISO strings.\n"
        "If insufficient evidence, return an empty list.\n"
        "Provide up to: 6 roles, 10 interests, 6 specialties, 6 style, 6 recent_activities.\n"
        "Recent activities should summarize themes or tendencies, not individual events.\n\n"
        "Evidence:\n"
        f"Event summaries (use refs or event_id from this list only): {event_summaries}\n"
        f"Recent event summaries (last {recent_days} days; use refs R1..): {recent_event_summaries}\n"
        f"Topic bundles: {topic_bundles}\n"
        f"Top actions: {action_counts}\n"
        f"Top artifacts: {artifact_counts}\n"
        f"Top domains: {domain_counts}\n\n"
        "Output format example:\n"
        "{\n"
        '  "roles": [{"label": "ai researcher", "description": "...", "confidence": 0.7, "evidence_event_refs": ["E1"]}],\n'
        '  "interests": [{"label": "autonomous research agents", "description": "...", "confidence": 0.6, "evidence_event_refs": ["E2","E3"]}],\n'
        '  "specialties": [],\n'
        '  "style": [{"label": "structured_notes", "description": "...", "confidence": 0.6, "evidence_event_refs": ["E4"]}],\n'
        '  "recent_activities": [{"label": "literature survey on AI agents", "description": "...", "confidence": 0.8, "evidence_event_refs": ["R1","R2"]}]\n'
        "}\n"
    )
