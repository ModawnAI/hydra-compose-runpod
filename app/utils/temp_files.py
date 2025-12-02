"""Temporary file management."""

import os
import shutil
import time
import gc
from typing import Optional

from ..config import get_settings


class TempFileManager:
    """Manager for temporary files during rendering."""

    def __init__(self):
        settings = get_settings()
        # Normalize path for cross-platform compatibility
        self.base_dir = os.path.normpath(settings.temp_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def get_job_dir(self, job_id: str) -> str:
        """Get the directory for a specific job."""
        job_dir = os.path.join(self.base_dir, job_id)
        os.makedirs(job_dir, exist_ok=True)
        return job_dir

    def get_path(self, job_id: str, filename: str) -> str:
        """Get a path for a file within a job's directory."""
        job_dir = self.get_job_dir(job_id)
        return os.path.join(job_dir, filename)

    def cleanup(self, job_id: str, max_retries: int = 5) -> None:
        """Clean up all temporary files for a job with retry for Windows."""
        job_dir = os.path.join(self.base_dir, job_id)
        if not os.path.exists(job_dir):
            return

        # Force garbage collection to release file handles
        gc.collect()

        for attempt in range(max_retries):
            try:
                shutil.rmtree(job_dir)
                return
            except PermissionError as e:
                if attempt < max_retries - 1:
                    # Wait and retry (file handles may still be releasing)
                    time.sleep(0.5 * (attempt + 1))
                    gc.collect()
                else:
                    # Log but don't fail - files will be cleaned up later
                    print(f"Warning: Could not clean up {job_dir}: {e}")

    def cleanup_all(self) -> None:
        """Clean up all temporary files."""
        if os.path.exists(self.base_dir):
            for item in os.listdir(self.base_dir):
                item_path = os.path.join(self.base_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
