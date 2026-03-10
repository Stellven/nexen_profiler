from __future__ import annotations

import hashlib
import os
from typing import Dict, List

from app.llm.gemini_client import GeminiClient, select_gemini_model
from app.signals.types import SignalData


ACTION_LABELS = [
    "learn",
    "summarize",
    "research",
    "analyze",
    "compare",
    "decide",
    "plan",
    "organize",
    "monitor",
    "maintain",
    "implement",
    "create",
    "practice",
    "communicate",
    "collaborate",
    "debug",
]

_DEFAULT_MIN_CONF = 0.45
_DEFAULT_MAX_CHARS = 2400
_DEFAULT_MAX_LABELS = 4

_CLIENT: GeminiClient | None = None


def _get_client(model: str | None = None) -> GeminiClient:
    global _CLIENT
    if _CLIENT is None or (model and _CLIENT.model != model):
        _CLIENT = GeminiClient(model=model or select_gemini_model())
    return _CLIENT


def _snippet(text: str, limit: int) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "..."


def _env_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _build_prompt(event: Dict, text: str, min_conf: float, max_labels: int) -> str:
    labels = ", ".join(ACTION_LABELS)
    source = event.get("source") or "unknown"
    title = event.get("title") or ""
    uri = event.get("uri") or ""
    return (
        "You are labeling user actions implied by a piece of content. "
        "Choose only from the allowed labels. Return compact JSON only.\n\n"
        f"Allowed labels: [{labels}]\n"
        f"Minimum confidence: {min_conf}\n"
        f"Max labels: {max_labels}\n\n"
        "Content metadata:\n"
        f"- source: {source}\n"
        f"- title: {title}\n"
        f"- uri: {uri}\n\n"
        "Content excerpt:\n"
        f"{text}\n\n"
        "Output JSON schema:\n"
        "{\n"
        "  \"actions\": [\n"
        "    {\"label\": \"learn\", \"confidence\": 0.72},\n"
        "    ...\n"
        "  ]\n"
        "}\n"
        "Rules: Only include labels with confidence >= minimum confidence. "
        "Return an empty list when no actions apply."
    )


def action_signals_llm(event: Dict, model: str | None = None) -> List[SignalData]:
    min_conf = _env_float("ACTION_LLM_MIN_CONF", _DEFAULT_MIN_CONF)
    max_chars = _env_int("ACTION_LLM_MAX_CHARS", _DEFAULT_MAX_CHARS)
    max_labels = _env_int("ACTION_LLM_MAX_LABELS", _DEFAULT_MAX_LABELS)

    excerpt = _snippet(event.get("content_text") or "", max_chars)
    prompt = _build_prompt(event, excerpt, min_conf=min_conf, max_labels=max_labels)
    client = _get_client(model)
    result = client.generate_json(prompt)

    raw_actions = result.get("actions") or []
    best: Dict[str, float] = {}
    for item in raw_actions:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip().lower()
        if label not in ACTION_LABELS:
            continue
        try:
            conf = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))
        if conf < min_conf:
            continue
        if label not in best or conf > best[label]:
            best[label] = conf

    signals: List[SignalData] = []
    for label, conf in best.items():
        signal_id = hashlib.sha256(f"action:llm:{event['event_id']}:{label}".encode("utf-8")).hexdigest()
        signals.append(
            SignalData(
                signal_id=signal_id,
                event_id=event["event_id"],
                chunk_id=None,
                type="action",
                name=label,
                value={},
                confidence=conf,
                evidence_spans=[],
                computed_by={"method": "llm", "model": client.model, "version": "1.0"},
            )
        )
    return signals
