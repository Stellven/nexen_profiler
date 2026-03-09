from __future__ import annotations

from typing import Dict


_ACTION_TO_INTENT = {
    "learn": "learn",
    "summarize": "learn",
    "implement": "build",
    "debug": "build",
    "compare": "decide",
    "decide": "decide",
    "monitor": "monitor",
    "communicate": "communicate",
    "plan": "communicate",
}


def infer_intent(action_counts: Dict[str, int]) -> str:
    score: Dict[str, int] = {}
    for action, count in action_counts.items():
        intent = _ACTION_TO_INTENT.get(action)
        if not intent:
            continue
        score[intent] = score.get(intent, 0) + count
    if not score:
        return "unknown"
    return max(score.items(), key=lambda kv: kv[1])[0]
