from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.storage.models import Embedding


def upsert_embeddings(session: Session, chunk_ids: List[str], embeddings: List[List[float]], model_name: str) -> None:
    for chunk_id, vector in zip(chunk_ids, embeddings):
        existing = session.get(Embedding, chunk_id)
        if existing:
            existing.embedding = vector
            existing.model_name = model_name
            continue
        session.add(Embedding(chunk_id=chunk_id, embedding=vector, model_name=model_name))
