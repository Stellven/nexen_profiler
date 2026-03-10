from __future__ import annotations

from typing import Dict, List

from app.llm.gemini_client import GeminiClient, select_gemini_model
from app.projects.cluster_projects import ProjectData


INTENT_LABELS = [
    "learn",
    "analyze",
    "decide",
    "manage",
    "operate",
    "build",
    "communicate",
    "unknown",
]

_CLIENT: GeminiClient | None = None


def _get_client(model: str | None = None) -> GeminiClient:
    global _CLIENT
    if _CLIENT is None or (model and _CLIENT.model != model):
        _CLIENT = GeminiClient(model=model or select_gemini_model())
    return _CLIENT


def _build_prompt(summary: str) -> str:
    labels = ", ".join(INTENT_LABELS)
    return (
        "You are selecting a single project intent label based on evidence. "
        "Choose only from the allowed labels. Return compact JSON only.\n\n"
        f"Allowed labels: [{labels}]\n\n"
        "Project evidence:\n"
        f"{summary}\n\n"
        "Output JSON schema:\n"
        "{\n"
        "  \"intent\": \"build\",\n"
        "  \"confidence\": 0.73\n"
        "}\n"
        "Rules: Return intent=unknown when evidence is insufficient or ambiguous."
    )


def infer_intent_llm(project: ProjectData, action_counts: Dict[str, int], model: str | None = None) -> str:
    client = _get_client(model)

    actions = sorted(action_counts.items(), key=lambda kv: kv[1], reverse=True)[:12]
    action_summary = ", ".join(f"{name}:{count}" for name, count in actions) or "none"
    topics = ", ".join(sorted(project.topics)[:12]) or "none"
    entities = ", ".join(sorted(project.entities)[:12]) or "none"

    summary = (
        f"Title: {project.title}\n"
        f"Topics: {topics}\n"
        f"Entities: {entities}\n"
        f"Top actions: {action_summary}\n"
        f"Timeframe: {project.first_seen.isoformat()} -> {project.last_seen.isoformat()}\n"
    )

    result = client.generate_json(_build_prompt(summary))
    intent = str(result.get("intent") or "").strip().lower()
    if intent not in INTENT_LABELS:
        return "unknown"
    return intent
