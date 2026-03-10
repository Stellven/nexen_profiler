from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict


_DEFAULT_MODEL = "gemini-2.5-flash"
_MODEL_OPTIONS = [
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


def select_gemini_model() -> str:
    env_model = os.getenv("GEMINI_MODEL")
    if env_model:
        return env_model
    if not sys.stdin.isatty():
        return _DEFAULT_MODEL
    print("Select Gemini model:")
    for idx, name in enumerate(_MODEL_OPTIONS, 1):
        print(f"{idx}. {name}")
    choice = input(f"Enter number or model name [{_DEFAULT_MODEL}]: ").strip()
    if not choice:
        return _DEFAULT_MODEL
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(_MODEL_OPTIONS):
            return _MODEL_OPTIONS[idx - 1]
    return choice


class GeminiClient:
    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        try:
            from google import genai  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("google-genai is required for Gemini reasoning.") from exc
        self._genai = genai
        self.model = model or _DEFAULT_MODEL
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=key) if key else genai.Client()

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        result = self.client.models.generate_content(model=self.model, contents=prompt)
        text = getattr(result, "text", None) or ""
        return _extract_json(text)


def _extract_json(text: str) -> Dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
    # best-effort JSON extraction
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain JSON object.")
    payload = stripped[start : end + 1]
    return json.loads(payload)
