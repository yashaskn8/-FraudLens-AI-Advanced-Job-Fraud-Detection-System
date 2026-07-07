"""
Database connection and session management.
Uses SQLAlchemy async-compatible engine.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.config import settings

# Use SQLite fallback if PostgreSQL is not available
try:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    # Test connection
    with engine.connect() as conn:
        pass
except Exception:
    # Fallback to SQLite for development
    import os
    db_path = os.path.join(os.path.dirname(__file__), "..", "trusthire.db")
    SQLITE_URL = f"sqlite:///{db_path}"
    engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    from backend.models.job_scan import Base
    Base.metadata.create_all(bind=engine)
