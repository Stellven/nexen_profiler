from __future__ import annotations

from dataclasses import dataclass
from typing import List
import os


@dataclass
class EmbeddingResult:
    embeddings: List[List[float]]
    model_name: str


class Embedder:
    def embed(self, texts: List[str]) -> EmbeddingResult:
        raise NotImplementedError


class GeminiEmbedder(Embedder):
    def __init__(
        self,
        model: str | None = None,
        batch_size: int | None = None,
        api_key: str | None = None,
    ) -> None:
        try:
            from google import genai  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("google-genai is required for Gemini embeddings.") from exc

        self._genai = genai
        self.model = model or os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
        self.batch_size = batch_size or int(os.getenv("GEMINI_EMBED_BATCH", "100"))
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def embed(self, texts: List[str]) -> EmbeddingResult:
        client = self._genai.Client(api_key=self.api_key) if self.api_key else self._genai.Client()
        vectors: List[List[float]] = []
        total = len(texts)
        total_batches = max(1, (total + self.batch_size - 1) // self.batch_size)

        def _log(message: str) -> None:
            if os.getenv("NO_PROGRESS", "").lower() in {"1", "true", "yes", "y"}:
                return
            print(message, flush=True)

        for batch_idx, i in enumerate(range(0, total, self.batch_size), start=1):
            batch = texts[i : i + self.batch_size]
            start = i + 1
            end = i + len(batch)
            _log(
                f"[embed] Requesting batch {batch_idx}/{total_batches} "
                f"({len(batch)} chunks, items {start}-{end} of {total}) from {self.model}"
            )
            try:
                result = client.models.embed_content(model=self.model, contents=batch)
            except Exception as exc:
                _log(f"[embed] Batch {batch_idx}/{total_batches} failed: {exc}")
                raise
            embeddings = getattr(result, "embeddings", None) or []
            for embedding in embeddings:
                values = None
                if isinstance(embedding, dict):
                    values = embedding.get("values") or embedding.get("embedding")
                else:
                    values = getattr(embedding, "values", None)
                if values is None and isinstance(embedding, list):
                    values = embedding
                if values:
                    vectors.append([float(x) for x in values])
            _log(
                f"[embed] Received batch {batch_idx}/{total_batches}; "
                f"collected {len(vectors)}/{total} embeddings"
            )
        return EmbeddingResult(embeddings=vectors, model_name=self.model)


def resolve_embedder(default_dim: int) -> Embedder:
    _ = default_dim
    return GeminiEmbedder()
