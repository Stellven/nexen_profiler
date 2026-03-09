from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class LLMResponse:
    data: Dict[str, Any]


class LLMClient:
    def classify_actions(self, text: str, labels: List[str]) -> LLMResponse:
        raise NotImplementedError

    def name_topic(self, snippets: List[str]) -> LLMResponse:
        raise NotImplementedError

    def classify_intent(self, summary: str, labels: List[str]) -> LLMResponse:
        raise NotImplementedError
