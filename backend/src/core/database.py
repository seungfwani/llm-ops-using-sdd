from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _create_engine():
    settings = get_settings()
    # Convert AnyUrl to string for SQLAlchemy
    database_url_str = str(settings.database_url)
    return create_engine(
        database_url_str,
        echo=settings.sqlalchemy_echo,
        future=True,
    )


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

