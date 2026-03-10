-- Minimal init schema for Postgres + pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- The SQLAlchemy models define the canonical schema. This SQL is a minimal
-- reference for manual bootstrapping when needed.
