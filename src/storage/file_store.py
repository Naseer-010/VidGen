"""
DIME — File Storage Abstraction.

Local filesystem storage with interface compatible for S3 upgrade.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from src.config import settings

logger = logging.getLogger(__name__)


class FileStore:
    """Local filesystem storage for videos and assets."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or settings.output_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, source_path: str, dest_name: str) -> str:
        """Copy a file to storage. Returns the stored path."""
        dest = self.base_dir / dest_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest)
        logger.info("Stored: %s → %s", source_path, dest)
        return str(dest)

    def get_path(self, filename: str) -> Path:
        """Get full path for a stored file."""
        return self.base_dir / filename

    def exists(self, filename: str) -> bool:
        """Check if file exists in storage."""
        return (self.base_dir / filename).exists()

    def get_url(self, filename: str) -> str:
        """Get the URL for a stored video file."""
        return f"/videos/{filename}"

    def create_job_dir(self, job_id: str) -> Path:
        """Create and return a job-specific working directory."""
        job_dir = self.base_dir / "jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def cleanup_job(self, job_id: str) -> None:
        """Remove temporary job files after completion."""
        job_dir = self.base_dir / "jobs" / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)
            logger.info("Cleaned up job dir: %s", job_dir)


# Singleton
file_store = FileStore()
