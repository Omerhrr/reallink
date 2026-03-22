"""
Shared Dependencies for RealLink Ecosystem
Centralized database session management
"""

import os
from typing import Generator

from sqlalchemy.orm import Session

from app.models import get_engine, get_session_maker


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.
    Yields a session and ensures it's closed after use.
    """
    engine = get_engine(os.getenv("DATABASE_URL", "sqlite:///./reallink.db"))
    SessionLocal = get_session_maker(engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
