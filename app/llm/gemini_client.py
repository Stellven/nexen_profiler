from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any, Callable, Dict, TypeVar


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
_RETRYABLE_CODES = {429, 500, 502, 503, 504}
_RETRYABLE_STATUSES = {
    "DEADLINE_EXCEEDED",
    "INTERNAL",
    "RESOURCE_EXHAUSTED",
    "UNAVAILABLE",
}
_RETRY_DELAY_PATTERN = re.compile(r"retry in ([0-9]+(?:\.[0-9]+)?)s", re.IGNORECASE)
_DURATION_PATTERN = re.compile(r"^([0-9]+(?:\.[0-9]+)?)s$")
T = TypeVar("T")


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


def _error_code(exc: Exception) -> int | None:
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    return None


def _error_status(exc: Exception) -> str:
    status = getattr(exc, "status", None)
    if isinstance(status, str) and status:
        return status.upper()
    return ""


def _iter_retry_details(payload: Any):
    if isinstance(payload, dict):
        details = payload.get("details")
        if isinstance(details, list):
            for item in details:
                yield item
        nested = payload.get("error")
        if isinstance(nested, dict):
            yield from _iter_retry_details(nested)


def _parse_duration_seconds(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    match = _DURATION_PATTERN.match(value.strip())
    if not match:
        return None
    return float(match.group(1))


def _retry_delay_seconds(exc: Exception) -> float | None:
    details = getattr(exc, "details", None)
    for item in _iter_retry_details(details):
        if not isinstance(item, dict):
            continue
        delay = _parse_duration_seconds(item.get("retryDelay"))
        if delay is not None:
            return delay

    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
        header_delay = _parse_duration_seconds(headers.get("retry-after"))
        if header_delay is not None:
            return header_delay
        raw_retry_after = headers.get("retry-after")
        if isinstance(raw_retry_after, str):
            try:
                return float(raw_retry_after)
            except ValueError:
                pass

    message = getattr(exc, "message", None)
    if not isinstance(message, str):
        message = str(exc)
    match = _RETRY_DELAY_PATTERN.search(message)
    if not match:
        return None
    return float(match.group(1))


def _is_retryable_gemini_error(exc: Exception) -> bool:
    code = _error_code(exc)
    status = _error_status(exc)
    return (code in _RETRYABLE_CODES) or (status in _RETRYABLE_STATUSES)


def call_with_gemini_retry(
    fn: Callable[[], T],
    *,
    operation_name: str,
    log: Callable[[str], None] | None = None,
) -> T:
    try:
        max_attempts = max(1, int(os.getenv("GEMINI_MAX_RETRIES", "6")))
    except ValueError:
        max_attempts = 6
    try:
        max_wait = max(1.0, float(os.getenv("GEMINI_RETRY_MAX_WAIT_SECONDS", "120")))
    except ValueError:
        max_wait = 120.0

    attempt = 1
    while True:
        try:
            return fn()
        except Exception as exc:
            if attempt >= max_attempts or not _is_retryable_gemini_error(exc):
                raise
            code = _error_code(exc)
            retry_after = _retry_delay_seconds(exc)
            if retry_after is None:
                retry_after = 60.0 if code == 429 else min(5.0 * (2 ** (attempt - 1)), max_wait)
            retry_after = min(max(retry_after, 1.0), max_wait)
            if log is not None:
                log(
                    f"[gemini] {operation_name} hit a retryable error "
                    f"(attempt {attempt}/{max_attempts}): waiting {retry_after:.1f}s"
                )
            time.sleep(retry_after)
            attempt += 1


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
        result = call_with_gemini_retry(
            lambda: self.client.models.generate_content(model=self.model, contents=prompt),
            operation_name=f"generate_content:{self.model}",
        )
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
