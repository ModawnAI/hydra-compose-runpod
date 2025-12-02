"""FastAPI dependencies for Compose Engine."""

import asyncio
from .utils.job_queue import JobQueue

# Global job queue instance - set by main.py lifespan
_job_queue: JobQueue = None

# Semaphore for controlling concurrent render jobs
_render_semaphore: asyncio.Semaphore = None


def set_job_queue(queue: JobQueue):
    """Set the global job queue instance (called during app startup)."""
    global _job_queue
    _job_queue = queue


def get_job_queue() -> JobQueue:
    """Get the global job queue instance."""
    return _job_queue


def init_render_semaphore(max_concurrent: int):
    """Initialize the render semaphore with max concurrent jobs."""
    global _render_semaphore
    _render_semaphore = asyncio.Semaphore(max_concurrent)


def get_render_semaphore() -> asyncio.Semaphore:
    """Get the render semaphore for concurrency control."""
    return _render_semaphore
