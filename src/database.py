"""
DIME — Database Layer (SQLAlchemy + SQLite).

Manages Job persistence and state tracking.
Easily swappable to PostgreSQL by changing DATABASE_URL in .env.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config import settings
from src.models import JobStatus

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════
# SQLAlchemy Base & Engine
# ═════════════════════════════════════════════════════════════


class Base(DeclarativeBase):
    pass


# Enable WAL mode for SQLite (better concurrent reads)
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if "sqlite" in settings.database_url
    else {},
    echo=False,
)

if "sqlite" in settings.database_url:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine)


# ═════════════════════════════════════════════════════════════
# Job Table
# ═════════════════════════════════════════════════════════════


class JobRecord(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), unique=True, nullable=False, index=True)
    status = Column(String(20), default=JobStatus.QUEUED.value, nullable=False)
    question_text = Column(Text, nullable=True)
    question_hash = Column(String(64), nullable=True, index=True)
    image_path = Column(String(512), nullable=True)
    brain_output_json = Column(Text, nullable=True)
    final_video_path = Column(String(512), nullable=True)
    video_url = Column(String(1024), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ═════════════════════════════════════════════════════════════
# Database Operations
# ═════════════════════════════════════════════════════════════


def init_db() -> None:
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created at %s", settings.database_url)


def get_session() -> Session:
    """Get a new DB session."""
    return SessionLocal()


def create_job(
    job_id: str,
    question_text: Optional[str] = None,
    question_hash: Optional[str] = None,
    image_path: Optional[str] = None,
) -> JobRecord:
    """Insert a new job record."""
    with get_session() as session:
        record = JobRecord(
            job_id=job_id,
            question_text=question_text,
            question_hash=question_hash,
            image_path=image_path,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        logger.info("Job %s created with hash %s", job_id, question_hash)
        return record


def get_job(job_id: str) -> Optional[JobRecord]:
    """Fetch a job by ID."""
    with get_session() as session:
        return session.query(JobRecord).filter_by(job_id=job_id).first()


def update_job_status(
    job_id: str,
    status: JobStatus,
    error_message: Optional[str] = None,
    final_video_path: Optional[str] = None,
    video_url: Optional[str] = None,
    brain_output_json: Optional[str] = None,
) -> None:
    """Update job status and optional fields."""
    with get_session() as session:
        record = session.query(JobRecord).filter_by(job_id=job_id).first()
        if record:
            record.status = status.value
            record.updated_at = datetime.utcnow()
            if error_message is not None:
                record.error_message = error_message
            if final_video_path is not None:
                record.final_video_path = final_video_path
            if video_url is not None:
                record.video_url = video_url
            if brain_output_json is not None:
                record.brain_output_json = brain_output_json
            session.commit()
            logger.info("Job %s → %s", job_id, status.value)


def find_job_by_hash(question_hash: str) -> Optional[JobRecord]:
    """Find a completed job with the same question hash (cache hit)."""
    with get_session() as session:
        return (
            session.query(JobRecord)
            .filter_by(question_hash=question_hash, status=JobStatus.COMPLETED.value)
            .order_by(JobRecord.created_at.desc())
            .first()
        )
