from __future__ import annotations

import os
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from sqlalchemy.orm import Session

from app.chunking.chunker import chunk_text
from app.embeddings.embedder import resolve_embedder
from app.embeddings.vector_store import upsert_embeddings
from app.ingestion.ingest_dirs import collect_inputs
from app.ingestion.normalize_events import EventData, normalize_events
from app.inference.llm_reasoner import LLMReasoner
from app.inference.types import InferenceItem
from app.pipeline.config import PipelineConfig, default_config, now_utc
from app.profile.assemble import assemble_profile, attach_default_signals, filter_inferences
from app.projects.cluster_projects import cluster_sessions
from app.projects.sessionize import sessionize
from app.projects.summarize_intent import infer_intent
from app.signals.actions import action_signals
from app.signals.artifacts import artifact_signals
from app.signals.entities import entity_signals
from app.signals.topics import TopicAssigner, topic_signal
from app.signals.types import SignalData
from app.storage.db import get_session, init_db
from app.storage.models import (
    Chunk,
    Embedding,
    Event,
    Inference,
    InferenceEventMap,
    InferenceSignalMap,
    Profile,
    Project,
    ProjectEventMap,
    Signal,
)
from app.llm.gemini_client import select_gemini_model

def _progress(iterable, desc: str, total: int | None = None):
    if os.getenv("NO_PROGRESS", "").lower() in {"1", "true", "yes", "y"}:
        return iterable
    if total is None:
        try:
            total = len(iterable)
        except Exception:
            total = None

    def _gen():
        count = 0
        last_printed = -1
        for item in iterable:
            count += 1
            if total and total > 0:
                percent = int((count / total) * 100)
                if percent != last_printed:
                    print(f"{desc} ({percent}%)", end="\r", flush=True)
                    last_printed = percent
            yield item
        if total and total > 0:
            print(f"{desc} (100%)")
        else:
            print(f"{desc} (100%)")

    return _gen()


def _step(msg: str) -> None:
    print(f"[pipeline] {msg}")


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class PipelineRunner:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.embedder = resolve_embedder(config.embedding_dim)
        self.topic_assigner = TopicAssigner(threshold=config.topic_similarity_threshold)
        self.llm_reasoner: LLMReasoner | None = None
        # Prompt for LLM selection at startup for long-running pipelines.
        self.llm_model = select_gemini_model()

    def _resolve_roles_path(self) -> Path:
        env_path = os.getenv("ROLES_PATH")
        if env_path:
            return Path(env_path)
        candidates = [
            Path.cwd() / "prototypes" / "roles.yml",
            Path(__file__).resolve().parents[2] / "prototypes" / "roles.yml",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[-1]

    def _write_profile_md(self, profile: Dict, events_by_id: Dict[str, Dict], signals: List[SignalData]) -> Path:
        output_path = os.getenv("PROFILE_MD_PATH")
        generated_at = profile.get("generated_at")
        try:
            generated_dt = datetime.fromisoformat(generated_at) if generated_at else now_utc()
        except Exception:
            generated_dt = now_utc()
        timestamp = generated_dt.astimezone(timezone.utc).strftime("%Y%m%d_%H%M%S")

        if output_path:
            base = Path(output_path)
            if base.suffix.lower() == ".md":
                filename = f"{base.stem}_{timestamp}{base.suffix}"
                path = base.with_name(filename)
            else:
                base.mkdir(parents=True, exist_ok=True)
                path = base / f"profile_{timestamp}.md"
        else:
            path = Path.cwd() / f"profile_{timestamp}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        counter = 1
        while path.exists():
            path = path.with_name(f"{path.stem}_{counter}{path.suffix}")
            counter += 1

        signals_by_id = {s.signal_id: s for s in signals}

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

        def _event_summary(event_ids: List[str], limit: int = 5) -> str:
            events = [events_by_id.get(eid) for eid in event_ids if events_by_id.get(eid)]
            if not events:
                return t["none"]
            events.sort(key=lambda ev: ev.get("timestamp"), reverse=True)
            parts = []
            for ev in events[:limit]:
                label = _event_label(ev)
                source = ev.get("source") or "unknown"
                ts = ev.get("timestamp")
                date_str = ts.date().isoformat() if ts else "unknown"
                parts.append(f"{label} ({source}, {date_str})")
            if len(events) > limit:
                parts.append(f"+{len(events) - limit} more")
            return "; ".join(parts)

        def _signal_summary(signal_ids: List[str]) -> str:
            if not signal_ids:
                return t["none"]
            grouped: Dict[str, Dict[str, int]] = {"topic": {}, "action": {}, "artifact": {}, "entity": {}}
            for sid in signal_ids:
                sig = signals_by_id.get(sid)
                if not sig:
                    continue
                if sig.type == "entity":
                    ent_type = sig.value.get("type") if isinstance(sig.value, dict) else None
                    if ent_type not in {"domain", "import"}:
                        continue
                grouped.setdefault(sig.type, {})
                grouped[sig.type][sig.name] = grouped[sig.type].get(sig.name, 0) + 1
            lines: List[str] = []
            for key, label in (("topic", "Topics"), ("action", "Actions"), ("artifact", "Artifacts"), ("entity", "Entities")):
                counts = grouped.get(key, {})
                if not counts:
                    continue
                top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:8]
                values = ", ".join(f"{name}" for name, _ in top)
                lines.append(f"{label}: {values}")
            return " | ".join(lines) if lines else t["none"]

        lang = (self.config.profile_language or "en").lower()
        text = {
            "en": {
                "portrait_title": "User Profile / Portrait",
                "overall": "Overall Portrait",
                "primary_identity": "Primary identity",
                "core_focus": "Core focus",
                "secondary_interests": "Secondary interests",
                "strengths": "Strengths",
                "style": "Style",
                "observed": "Observed Facts",
                "summary": "Summary",
                "description": "Description",
                "time_frame": "Time frame",
                "evidence": "Evidence",
                "events": "Events",
                "signals": "Signals",
                "none": "None",
                "unknown": "unknown",
                "insufficient": "insufficient evidence",
            },
            "zh": {
                "portrait_title": "用户画像 / Portrait",
                "overall": "整体画像",
                "primary_identity": "核心身份",
                "core_focus": "核心关注",
                "secondary_interests": "次要兴趣",
                "strengths": "优势",
                "style": "风格",
                "observed": "观察到的事实",
                "summary": "摘要",
                "description": "描述",
                "time_frame": "时间范围",
                "evidence": "证据",
                "events": "事件",
                "signals": "信号",
                "none": "无",
                "unknown": "未知",
                "insufficient": "证据不足",
            },
        }
        t = text["zh"] if lang.startswith("zh") else text["en"]

        def fmt_section(title: str, items: List[Dict]) -> List[str]:
            lines = [f"## {title}"]
            if not items:
                lines.append(t["none"])
                lines.append("")
                return lines
            summary_labels = ", ".join(i.get("label", "unknown") for i in items[:12])
            lines.append(f"{t['summary']}: {summary_labels}")
            lines.append("")
            for idx, item in enumerate(items, 1):
                label = item.get("label", "unknown")
                desc = item.get("description", "")
                tf = item.get("time_frame") or {}
                start = tf.get("start", "unknown")
                end = tf.get("end", "unknown")
                confidence = item.get("confidence")
                if confidence is not None:
                    lines.append(f"{idx}. **{label}** (confidence: {confidence})<br>")
                else:
                    lines.append(f"{idx}. **{label}**<br>")
                lines.append(f"• {t['description']}: {desc or t['none']}<br>")
                lines.append(f"• {t['time_frame']}: {start} → {end}<br>")
                evidence = item.get("evidence") or {}
                ev_ids = evidence.get("event_ids") or []
                sig_ids = evidence.get("signal_ids") or []
                lines.append(f"• {t['evidence']}:<br>")
                lines.append(f"• {t['events']} ({len(ev_ids)}): {_event_summary(ev_ids)}<br>")
                lines.append(f"• {t['signals']}: {_signal_summary(sig_ids)}")
                lines.append("")
            return lines

        def _top_facts(title: str, values: Dict[str, int], limit: int = 8) -> List[str]:
            if not values:
                return [f"{title}: None"]
            top = sorted(values.items(), key=lambda kv: kv[1], reverse=True)[:limit]
            return [f"{title}: " + ", ".join(f"{k} ({v})" for k, v in top)]

        profile_view = profile.get("profile_view", {})
        observed_facts = profile.get("observed_facts", {})

        roles = profile_view.get("roles", [])
        interests = profile_view.get("interests", [])
        specialties = profile_view.get("specialties", [])
        styles = profile_view.get("style", [])

        def _top_labels(items: List[Dict], limit: int = 3, min_conf: float = 0.5) -> List[str]:
            filtered = [i for i in items if (i.get("confidence") or 0) >= min_conf]
            filtered.sort(key=lambda i: i.get("confidence") or 0, reverse=True)
            return [i.get("label", "unknown") for i in filtered[:limit]]

        lines = [
            f"# {t['portrait_title']}",
            f"Generated at: {profile.get('generated_at', 'unknown')}",
            f"Schema version: {profile.get('schema_version', 'unknown')}",
            "",
        ]
        # Portrait summary near the top for quick scanning
        lines.append(f"## {t['overall']}")
        primary_roles = _top_labels(roles, limit=2, min_conf=0.55)
        core_focus = _top_labels(interests, limit=5, min_conf=0.6)
        secondary = _top_labels(interests, limit=5, min_conf=0.4)
        secondary = [x for x in secondary if x not in core_focus]
        primary_specs = _top_labels(specialties, limit=3, min_conf=0.6)
        style_labels = _top_labels(styles, limit=3, min_conf=0.5)
        lines.append(f"{t['primary_identity']}: {', '.join(primary_roles) if primary_roles else t['unknown']}")
        lines.append(f"{t['core_focus']}: {', '.join(core_focus) if core_focus else t['insufficient']}")
        if secondary:
            lines.append(f"{t['secondary_interests']}: {', '.join(secondary)}")
        if primary_specs:
            lines.append(f"{t['strengths']}: {', '.join(primary_specs)}")
        if style_labels:
            lines.append(f"{t['style']}: {', '.join(style_labels)}")
        lines.append("")

        lines.append(f"## {t['observed']}")
        lines.extend(_top_facts("Top topics", observed_facts.get("topics") or {}))
        lines.extend(_top_facts("Top entities", observed_facts.get("entities") or {}))
        lines.extend(_top_facts("Top actions", observed_facts.get("actions") or {}))
        lines.extend(_top_facts("Top artifacts", observed_facts.get("artifacts") or {}))
        lines.append("")
        lines += fmt_section("Roles", profile_view.get("roles", []))
        lines += fmt_section("Interests", profile_view.get("interests", []))
        lines += fmt_section("Specialties", profile_view.get("specialties", []))
        lines += fmt_section("Style", profile_view.get("style", []))
        lines += fmt_section("Recent Activities", profile_view.get("recent_activities", []))

        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return path

    def run(self) -> Dict:
        init_db(self.config.db_url)
        _step("Collecting inputs")
        raw_inputs = collect_inputs(self.config)
        _step(f"Normalizing {len(raw_inputs)} inputs")
        events = normalize_events(self.config, raw_inputs)

        with get_session(self.config.db_url) as session:
            _step(f"Upserting {len(events)} events")
            self._upsert_events(session, events)
            session.flush()
            db_events = self._load_events(session)
            _step(f"Ensuring chunks for {len(db_events)} events")
            chunks = self._ensure_chunks(session, db_events)
            _step(f"Ensuring embeddings for {len(chunks)} chunks")
            self._ensure_embeddings(session, chunks)
            _step(f"Ensuring signals for {len(db_events)} events")
            signals = self._ensure_signals(session, db_events, chunks)
            _step("Building projects")
            projects = self._build_projects(session, db_events, signals)
            _step("Inferring profile signals")
            inferences = self._infer(db_events, signals)
            attach_default_signals(inferences, signals)
            inferences = filter_inferences(inferences)
            _step(f"Storing {len(inferences)} inferences")
            self._store_inferences(session, inferences)
            _step("Storing profile")
            profile_json = self._store_profile(session, db_events, signals, projects, inferences)
            events_by_id = {ev["event_id"]: ev for ev in db_events}
            md_path = self._write_profile_md(profile_json, events_by_id, signals)
            _step(f"Wrote profile markdown to {md_path}")
            return profile_json

    def _upsert_events(self, session: Session, events: List[EventData]) -> None:
        for event in _progress(events, "Events", total=len(events)):
            if session.get(Event, event.event_id):
                continue
            session.add(
                Event(
                    event_id=event.event_id,
                    user_id=event.user_id,
                    source=event.source,
                    timestamp=event.timestamp,
                    timestamp_quality=event.timestamp_quality,
                    uri=event.uri,
                    title=event.title,
                    content_type=event.content_type,
                    content_text=event.content_text,
                    metadata_json=event.metadata,
                    content_hash=event.content_hash,
                )
            )

    def _load_events(self, session: Session) -> List[Dict]:
        db_events = session.query(Event).filter_by(user_id=self.config.user_id).all()
        return [
            {
                "event_id": ev.event_id,
                "user_id": ev.user_id,
                "source": ev.source,
                "timestamp": _ensure_aware(ev.timestamp),
                "timestamp_quality": ev.timestamp_quality,
                "uri": ev.uri,
                "title": ev.title,
                "content_type": ev.content_type,
                "content_text": ev.content_text,
                "metadata": ev.metadata_json,
            }
            for ev in db_events
        ]

    def _ensure_chunks(self, session: Session, events: List[Dict]) -> List[Chunk]:
        chunks: List[Chunk] = []
        for event in _progress(events, "Chunks", total=len(events)):
            existing = session.query(Chunk).filter_by(event_id=event["event_id"]).first()
            if existing:
                chunks.extend(session.query(Chunk).filter_by(event_id=event["event_id"]).all())
                continue
            for chunk in chunk_text(event["event_id"], event["content_text"]):
                model = Chunk(
                    chunk_id=chunk.chunk_id,
                    event_id=chunk.event_id,
                    start_offset=chunk.start_offset,
                    end_offset=chunk.end_offset,
                    span_hash=chunk.span_hash,
                    chunk_text=chunk.chunk_text,
                )
                session.add(model)
                chunks.append(model)
        return chunks

    def _ensure_embeddings(self, session: Session, chunks: List[Chunk]) -> None:
        missing = [c for c in chunks if not session.get(Embedding, c.chunk_id)]
        if not missing:
            return
        _step(f"Embedding {len(missing)} chunks")
        texts = [c.chunk_text for c in missing]
        model_hint = getattr(self.embedder, "model", None) or "unknown"
        desc = f"Embedding model: {model_hint}"
        if os.getenv("NO_PROGRESS", "").lower() not in {"1", "true", "yes", "y"}:
            print(f"{desc} (0%)", end="\r", flush=True)
        result = self.embedder.embed(texts)
        if not result.embeddings or len(result.embeddings) != len(texts):
            raise RuntimeError(
                f"Embedding failed: expected {len(texts)} vectors, got {len(result.embeddings)}."
            )
        final_desc = f"Embedding model: {result.model_name}"
        if os.getenv("NO_PROGRESS", "").lower() not in {"1", "true", "yes", "y"}:
            print(f"{final_desc} (100%)")
        upsert_embeddings(session, [c.chunk_id for c in missing], result.embeddings, result.model_name)

    def _ensure_signals(self, session: Session, events: List[Dict], chunks: List[Chunk]) -> List[SignalData]:
        signals: List[SignalData] = []
        chunks_by_event = {}
        for chunk in chunks:
            chunks_by_event.setdefault(chunk.event_id, []).append(chunk)
        for event in _progress(events, "Signals", total=len(events)):
            if session.query(Signal).filter_by(event_id=event["event_id"]).first():
                continue
            signals.extend(artifact_signals(event["event_id"], event["content_type"]))
            signals.extend(entity_signals(event["event_id"], event["uri"], event["content_text"]))
            for chunk in chunks_by_event.get(event["event_id"], []):
                signals.extend(action_signals(event["event_id"], chunk.chunk_id, chunk.chunk_text))
                embedding = session.get(Embedding, chunk.chunk_id)
                if embedding is not None:
                    topic = self.topic_assigner.assign(list(embedding.embedding), chunk.chunk_text)
                    signals.append(topic_signal(event["event_id"], chunk.chunk_id, topic.label))
        for signal in signals:
            if session.get(Signal, signal.signal_id):
                continue
            session.add(
                Signal(
                    signal_id=signal.signal_id,
                    event_id=signal.event_id,
                    chunk_id=signal.chunk_id,
                    type=signal.type,
                    name=signal.name,
                    value_json=signal.value,
                    confidence=signal.confidence,
                    evidence_spans_json=signal.evidence_spans,
                    computed_by_json=signal.computed_by,
                )
            )
        session.flush()
        db_signals = session.query(Signal).all()
        return [
            SignalData(
                signal_id=s.signal_id,
                event_id=s.event_id,
                chunk_id=s.chunk_id,
                type=s.type,
                name=s.name,
                value=s.value_json,
                confidence=s.confidence,
                evidence_spans=s.evidence_spans_json,
                computed_by=s.computed_by_json,
            )
            for s in db_signals
        ]

    def _build_projects(self, session: Session, events: List[Dict], signals: List[SignalData]) -> List[Dict]:
        event_topics: Dict[str, set] = {}
        event_entities: Dict[str, set] = {}
        action_counts_by_event: Dict[str, Dict[str, int]] = {}
        for signal in signals:
            if signal.type == "topic":
                event_topics.setdefault(signal.event_id, set()).add(signal.name)
            if signal.type == "entity":
                event_entities.setdefault(signal.event_id, set()).add(signal.name)
            if signal.type == "action":
                action_counts_by_event.setdefault(signal.event_id, {})
                action_counts_by_event[signal.event_id][signal.name] = (
                    action_counts_by_event[signal.event_id].get(signal.name, 0) + 1
                )
        sessions = sessionize(events, event_topics, self.config.session_gap_minutes)
        session_entities = []
        for sess in sessions:
            entities = set()
            for eid in sess.event_ids:
                entities.update(event_entities.get(eid, set()))
            session_entities.append(entities)
        projects = cluster_sessions(sessions, session_entities)
        now = now_utc()
        for project in projects:
            action_counts: Dict[str, int] = {}
            for eid in project.event_ids:
                for action, count in action_counts_by_event.get(eid, {}).items():
                    action_counts[action] = action_counts.get(action, 0) + count
            project.intent = infer_intent(action_counts)
            days_since = (now - project.last_seen).days
            if days_since <= 14:
                project.status = "active"
            elif days_since <= 60:
                project.status = "cooling"
            else:
                project.status = "dormant"
            if session.get(Project, project.project_id):
                existing = session.get(Project, project.project_id)
                existing.title = project.title
                existing.intent = project.intent
                existing.status = project.status
                existing.first_seen = project.first_seen
                existing.last_seen = project.last_seen
                existing.confidence = project.confidence
                existing.topics_json = sorted(project.topics)
                existing.entities_json = sorted(project.entities)
            else:
                session.add(
                    Project(
                        project_id=project.project_id,
                        user_id=self.config.user_id,
                        title=project.title,
                        intent=project.intent,
                        status=project.status,
                        first_seen=project.first_seen,
                        last_seen=project.last_seen,
                        confidence=project.confidence,
                        topics_json=sorted(project.topics),
                        entities_json=sorted(project.entities),
                    )
                )
            for event_id in project.event_ids:
                if not session.query(ProjectEventMap).filter_by(project_id=project.project_id, event_id=event_id).first():
                    session.add(ProjectEventMap(project_id=project.project_id, event_id=event_id))
        session.flush()
        return [
            {
                "project_id": p.project_id,
                "title": p.title,
                "intent": p.intent,
                "status": p.status,
                "first_seen": p.first_seen.isoformat(),
                "last_seen": p.last_seen.isoformat(),
                "confidence": p.confidence,
                "topics": p.topics_json,
                "entities": p.entities_json,
            }
            for p in session.query(Project).filter_by(user_id=self.config.user_id).all()
        ]

    def _infer(self, events: List[Dict], signals: List[SignalData]) -> List[InferenceItem]:
        events_by_id = {ev["event_id"]: ev for ev in events}
        if self.llm_reasoner is None:
            self.llm_reasoner = LLMReasoner(self._resolve_roles_path(), model=self.llm_model)
            _step(f"LLM reasoning enabled (Gemini model: {self.llm_reasoner.model})")
        llm_items = self.llm_reasoner.infer(
            self.config.user_id,
            events_by_id,
            signals,
            fingerprint_days=self.config.fingerprint_days,
            recent_days=self.config.recent_days,
            language=self.config.profile_language,
        )
        return llm_items

    def _store_inferences(self, session: Session, inferences: List[InferenceItem]) -> None:
        for inference in inferences:
            existing = session.get(Inference, inference.inference_id)
            if existing:
                existing.label = inference.label
                existing.description = inference.description
                existing.category = inference.category
                existing.probability = inference.probability
                existing.confidence = inference.confidence
                existing.first_seen = inference.first_seen
                existing.last_seen = inference.last_seen
                existing.start = inference.first_seen
                existing.end = inference.last_seen
                existing.method_json = inference.method
            else:
                session.add(
                    Inference(
                        inference_id=inference.inference_id,
                        user_id=self.config.user_id,
                        category=inference.category,
                        label=inference.label,
                        description=inference.description,
                        probability=inference.probability,
                        confidence=inference.confidence,
                        first_seen=inference.first_seen,
                        last_seen=inference.last_seen,
                        start=inference.first_seen,
                        end=inference.last_seen,
                        method_json=inference.method,
                    )
                )
            session.query(InferenceSignalMap).filter_by(inference_id=inference.inference_id).delete()
            session.query(InferenceEventMap).filter_by(inference_id=inference.inference_id).delete()
            for signal_id in inference.evidence_signal_ids:
                session.add(
                    InferenceSignalMap(
                        inference_id=inference.inference_id,
                        signal_id=signal_id,
                        contribution=1.0,
                    )
                )
            for event_id in inference.evidence_event_ids:
                session.add(
                    InferenceEventMap(
                        inference_id=inference.inference_id,
                        event_id=event_id,
                    )
                )

    def _store_profile(
        self,
        session: Session,
        events: List[Dict],
        signals: List[SignalData],
        projects: List[Dict],
        inferences: List[InferenceItem],
    ) -> Dict:
        generated_at = now_utc()
        profile = assemble_profile(generated_at, events, signals, projects, inferences)
        profile_json = {
            "observed_facts": profile.observed_facts,
            "user_state": profile.user_state,
            "profile_view": profile.profile_view,
            "capability_pack": profile.capability_pack,
            "explainability": profile.explainability,
            "generated_at": generated_at.isoformat(),
            "schema_version": "v1.1",
        }
        existing = session.get(Profile, self.config.user_id)
        if existing:
            existing.profile_json = profile_json
            existing.generated_at = generated_at
        else:
            session.add(
                Profile(
                    user_id=self.config.user_id,
                    profile_json=profile_json,
                    generated_at=generated_at,
                    schema_version="v1.1",
                )
            )
        return profile_json


def main() -> None:
    config = default_config(Path.cwd())
    runner = PipelineRunner(config)
    runner.run()
    print("Pipeline complete. Profile saved.")


if __name__ == "__main__":
    main()
