from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.storage.models import Base


def create_db_engine(db_url: str) -> Engine:
    return create_engine(db_url, future=True)


@contextmanager
def get_session(db_url: str) -> Iterator:
    engine = create_db_engine(db_url)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(db_url: str) -> None:
    engine = create_db_engine(db_url)
    Base.metadata.create_all(engine)
