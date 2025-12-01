from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DisconnectionError, OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _create_engine():
    settings = get_settings()
    # Convert AnyUrl to string for SQLAlchemy
    database_url_str = str(settings.database_url)
    
    # Connection pool settings for better reliability
    engine = create_engine(
        database_url_str,
        echo=settings.sqlalchemy_echo,
        future=True,
        # Connection pool settings
        pool_size=5,  # Number of connections to maintain
        max_overflow=10,  # Maximum number of connections beyond pool_size
        pool_pre_ping=True,  # Verify connections before using (handles stale connections)
        pool_recycle=3600,  # Recycle connections after 1 hour
        connect_args={
            "connect_timeout": 10,  # Connection timeout in seconds
            "keepalives": 1,  # Enable TCP keepalives
            "keepalives_idle": 30,  # Seconds before sending first keepalive
            "keepalives_interval": 10,  # Seconds between keepalives
            "keepalives_count": 5,  # Number of keepalives before considering connection dead
        },
    )
    
    # Add connection event listeners for better error handling
    @event.listens_for(engine, "connect")
    def set_connection_timeout(dbapi_conn, connection_record):
        """Set connection-level timeouts."""
        try:
            # Set statement timeout (30 seconds)
            with dbapi_conn.cursor() as cursor:
                cursor.execute("SET statement_timeout = 30000")
        except Exception as e:
            logger.warning(f"Failed to set connection timeout: {e}")
    
    return engine


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session with retry logic."""
    session = SessionLocal()
    try:
        yield session
    except (OperationalError, DisconnectionError) as e:
        # Log the error and close the session
        logger.error(f"Database connection error: {e}")
        session.rollback()
        session.close()
        # Re-raise to let the error handler middleware catch it
        raise
    except Exception as e:
        # Rollback on any other exception
        logger.error(f"Database error: {e}")
        session.rollback()
        raise
    finally:
        session.close()

