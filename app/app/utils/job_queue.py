"""Redis-based job queue for managing render jobs."""

import json
import logging
from typing import Optional, Callable, Any
from datetime import datetime

# Make redis import optional for Modal deployment (redis not needed there)
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None  # type: ignore
    REDIS_AVAILABLE = False
    logging.warning("Redis not available - using in-memory job store only")

from ..models.responses import JobStatus, JobStatusResponse

logger = logging.getLogger(__name__)


class InMemoryJobStore:
    """In-memory fallback when Redis is unavailable."""

    def __init__(self):
        self._jobs: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int = None) -> None:
        self._jobs[key] = value

    async def get(self, key: str) -> Optional[str]:
        return self._jobs.get(key)

    async def delete(self, key: str) -> None:
        self._jobs.pop(key, None)

    async def close(self) -> None:
        pass


class JobQueue:
    """Redis-based job queue for render jobs with in-memory fallback."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client: Optional[Any] = None  # Can be Redis or InMemoryJobStore
        self.is_connected = False
        self._fallback_store: Optional[InMemoryJobStore] = None

    async def connect(self) -> None:
        """Connect to Redis with graceful fallback."""
        # If redis module is not available, use in-memory store immediately
        if not REDIS_AVAILABLE or redis is None:
            logger.info("Redis module not available, using in-memory job store")
            self._fallback_store = InMemoryJobStore()
            self.client = self._fallback_store
            self.is_connected = False
            return

        try:
            self.client = redis.from_url(self.redis_url)
            await self.client.ping()
            self.is_connected = True
            logger.info("✅ Connected to Redis")
        except Exception as e:
            logger.warning(f"⚠️ Redis unavailable ({e}), using in-memory job store")
            self._fallback_store = InMemoryJobStore()
            self.client = self._fallback_store
            self.is_connected = False

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.client:
            await self.client.close()

    async def create_job(self, job_id: str, data: dict) -> None:
        """Create a new job entry."""
        job_data = {
            "job_id": job_id,
            "status": JobStatus.QUEUED.value,
            "progress": 0,
            "current_step": "Queued",
            "created_at": datetime.utcnow().isoformat(),
            "data": data
        }
        await self.client.set(
            f"compose:job:{job_id}",
            json.dumps(job_data),
            ex=86400  # Expire after 24 hours
        )

    async def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        progress: Optional[int] = None,
        current_step: Optional[str] = None,
        output_url: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> None:
        """Update job status."""
        job_data = await self.get_job(job_id)
        if not job_data:
            return

        if status:
            # Handle both Enum and string status values
            job_data["status"] = status.value if hasattr(status, 'value') else status
        if progress is not None:
            job_data["progress"] = progress
        if current_step:
            job_data["current_step"] = current_step
        if output_url:
            job_data["output_url"] = output_url
        if error:
            job_data["error"] = error
        if metadata:
            job_data["metadata"] = metadata

        job_data["updated_at"] = datetime.utcnow().isoformat()

        await self.client.set(
            f"compose:job:{job_id}",
            json.dumps(job_data),
            ex=86400
        )

    async def get_job(self, job_id: str) -> Optional[dict]:
        """Get job data by ID."""
        data = await self.client.get(f"compose:job:{job_id}")
        if data:
            return json.loads(data)
        return None

    async def get_job_status(self, job_id: str) -> Optional[JobStatusResponse]:
        """Get job status response."""
        job_data = await self.get_job(job_id)
        if not job_data:
            return None

        return JobStatusResponse(
            job_id=job_id,
            status=JobStatus(job_data.get("status", "queued")),
            progress=job_data.get("progress", 0),
            current_step=job_data.get("current_step"),
            output_url=job_data.get("output_url"),
            error=job_data.get("error")
        )

    async def delete_job(self, job_id: str) -> None:
        """Delete a job entry."""
        await self.client.delete(f"compose:job:{job_id}")


async def create_progress_callback(
    job_queue: JobQueue,
    job_id: str
) -> Callable[[str, int, str], Any]:
    """Create a progress callback function for the renderer."""

    async def callback(job_id: str, progress: int, step: str):
        status = JobStatus.PROCESSING
        if progress >= 100:
            status = JobStatus.COMPLETED
        await job_queue.update_job(
            job_id,
            status=status,
            progress=progress,
            current_step=step
        )

    return callback
