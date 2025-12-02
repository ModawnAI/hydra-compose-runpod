"""FastAPI application entry point for Compose Engine."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import logging

from .config import get_settings
from .utils.job_queue import JobQueue
from .dependencies import set_job_queue, init_render_semaphore

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    # Create temp directory
    os.makedirs(settings.temp_dir, exist_ok=True)

    # Initialize job queue
    job_queue = JobQueue(settings.redis_url)
    await job_queue.connect()
    set_job_queue(job_queue)

    # Initialize render semaphore for concurrent job control
    init_render_semaphore(settings.max_concurrent_jobs)
    logger.info(f"Render concurrency: max {settings.max_concurrent_jobs} parallel jobs")

    yield

    # Shutdown
    await job_queue.disconnect()


# Import routers after dependencies are set up to avoid circular imports
from .routers import render, images, audio, jobs, auto_compose


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="MoviePy-based video composition engine for HYDRA",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(render.router, prefix="/render", tags=["render"])
app.include_router(images.router, prefix="/images", tags=["images"])
app.include_router(audio.router, prefix="/audio", tags=["audio"])
app.include_router(jobs.router, prefix="/job", tags=["jobs"])
app.include_router(auto_compose.router, prefix="/api/v1/compose", tags=["auto-compose"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from .dependencies import get_job_queue
    job_queue = get_job_queue()
    return {
        "status": "healthy",
        "service": settings.app_name,
        "redis": "connected" if job_queue and job_queue.is_connected else "fallback (in-memory)"
    }
