from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.llm.gemini_client as gemini_client
from app.embeddings.embedder import GeminiEmbedder
from app.llm.gemini_client import call_with_gemini_retry


class RetryableGeminiError(Exception):
    def __init__(
        self,
        *,
        code: int = 429,
        status: str = "RESOURCE_EXHAUSTED",
        message: str = "Please retry in 2.5s.",
        details: dict | None = None,
    ) -> None:
        self.code = code
        self.status = status
        self.message = message
        self.details = details or {
            "error": {
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "2.5s",
                    }
                ]
            }
        }
        super().__init__(f"{code} {status}: {message}")


def test_call_with_gemini_retry_waits_for_retry_info(monkeypatch: pytest.MonkeyPatch):
    sleeps: list[float] = []
    attempts = {"count": 0}

    monkeypatch.setattr(gemini_client.time, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setenv("GEMINI_MAX_RETRIES", "3")

    def flaky_call():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RetryableGeminiError()
        return {"ok": True}

    assert call_with_gemini_retry(flaky_call, operation_name="test") == {"ok": True}
    assert attempts["count"] == 2
    assert sleeps == [2.5]


def test_embedder_retries_rate_limited_batch(monkeypatch: pytest.MonkeyPatch):
    sleeps: list[float] = []
    calls = {"count": 0}

    monkeypatch.setattr(gemini_client.time, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setenv("GEMINI_MAX_RETRIES", "3")

    def embed_content(*, model: str, contents: list[str]):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RetryableGeminiError()
        return SimpleNamespace(embeddings=[{"values": [0.1, 0.2, 0.3]} for _ in contents])

    fake_models = SimpleNamespace(embed_content=embed_content)
    fake_client = SimpleNamespace(models=fake_models)
    fake_genai = SimpleNamespace(Client=lambda api_key=None: fake_client)

    embedder = GeminiEmbedder.__new__(GeminiEmbedder)
    embedder._genai = fake_genai
    embedder.model = "gemini-embedding-001"
    embedder.batch_size = 10
    embedder.api_key = None

    result = embedder.embed(["hello world"])

    assert result.model_name == "gemini-embedding-001"
    assert result.embeddings == [[0.1, 0.2, 0.3]]
    assert calls["count"] == 2
    assert sleeps == [2.5]
