from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

try:
    from pgvector.sqlalchemy import Vector  # type: ignore
except Exception:  # pragma: no cover - pgvector optional in tests
    Vector = None

Base = declarative_base()
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "3072"))


def _vector_column(dim: int) -> Any:
    if Vector is None:
        return Column(JSON)
    return Column(Vector(dim))


class Event(Base):
    __tablename__ = "events"

    event_id = Column(String, primary_key=True)
    user_id = Column(String, index=True, nullable=False)
    source = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    timestamp_quality = Column(String, nullable=False)
    uri = Column(String, nullable=False)
    title = Column(String)
    content_type = Column(String, nullable=False)
    content_text = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=False, default=dict)
    content_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id = Column(String, primary_key=True)
    event_id = Column(String, ForeignKey("events.event_id"), index=True, nullable=False)
    start_offset = Column(Integer, nullable=False)
    end_offset = Column(Integer, nullable=False)
    span_hash = Column(String, nullable=False)
    chunk_text = Column(Text, nullable=False)


class Embedding(Base):
    __tablename__ = "embeddings"

    chunk_id = Column(String, ForeignKey("chunks.chunk_id"), primary_key=True)
    embedding = _vector_column(EMBEDDING_DIM)
    model_name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Signal(Base):
    __tablename__ = "signals"

    signal_id = Column(String, primary_key=True)
    event_id = Column(String, ForeignKey("events.event_id"), index=True, nullable=False)
    chunk_id = Column(String, ForeignKey("chunks.chunk_id"), index=True)
    type = Column(String, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    value_json = Column(JSON, nullable=False, default=dict)
    confidence = Column(Float, nullable=False, default=0.5)
    evidence_spans_json = Column(JSON, nullable=False, default=list)
    computed_by_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"

    project_id = Column(String, primary_key=True)
    user_id = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    intent = Column(String, nullable=False)
    status = Column(String, nullable=False)
    first_seen = Column(DateTime(timezone=True), nullable=False)
    last_seen = Column(DateTime(timezone=True), nullable=False)
    confidence = Column(Float, nullable=False)
    topics_json = Column(JSON, nullable=False, default=list)
    entities_json = Column(JSON, nullable=False, default=list)


class ProjectEventMap(Base):
    __tablename__ = "project_event_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey("projects.project_id"), index=True, nullable=False)
    event_id = Column(String, ForeignKey("events.event_id"), index=True, nullable=False)


class Inference(Base):
    __tablename__ = "inferences"

    inference_id = Column(String, primary_key=True)
    user_id = Column(String, index=True, nullable=False)
    category = Column(String, index=True, nullable=False)
    label = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    probability = Column(Float)
    confidence = Column(Float, nullable=False)
    first_seen = Column(DateTime(timezone=True))
    last_seen = Column(DateTime(timezone=True))
    start = Column(DateTime(timezone=True))
    end = Column(DateTime(timezone=True))
    method_json = Column(JSON, nullable=False, default=dict)


class InferenceSignalMap(Base):
    __tablename__ = "inference_signal_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inference_id = Column(String, ForeignKey("inferences.inference_id"), index=True, nullable=False)
    signal_id = Column(String, ForeignKey("signals.signal_id"), index=True, nullable=False)
    contribution = Column(Float, nullable=False, default=0.0)


class InferenceEventMap(Base):
    __tablename__ = "inference_event_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inference_id = Column(String, ForeignKey("inferences.inference_id"), index=True, nullable=False)
    event_id = Column(String, ForeignKey("events.event_id"), index=True, nullable=False)


class Profile(Base):
    __tablename__ = "profiles"

    user_id = Column(String, primary_key=True)
    profile_json = Column(JSON, nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=False)
    schema_version = Column(String, nullable=False, default="v1.1")
