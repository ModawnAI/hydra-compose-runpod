"""Pydantic models for API responses."""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class JobStatus(str, Enum):
    """Job status values."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStep(BaseModel):
    """A step in the rendering process."""
    name: str
    completed: bool
    progress: Optional[int] = None


class JobStatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str
    status: JobStatus
    progress: int = Field(default=0, ge=0, le=100)
    current_step: Optional[str] = None
    steps: Optional[list[JobStep]] = None
    output_url: Optional[str] = None
    error: Optional[str] = None


class AudioAnalysis(BaseModel):
    """Audio analysis result."""
    bpm: int = Field(..., description="Beats per minute")
    beat_times: list[float] = Field(..., description="Beat timestamps")
    energy_curve: list[tuple[float, float]] = Field(
        ...,
        description="Energy curve as (time, energy) pairs"
    )
    duration: float = Field(..., description="Audio duration in seconds")
    suggested_vibe: str = Field(..., description="Suggested vibe based on tempo")


class ImageCandidate(BaseModel):
    """Image search result candidate."""
    source_url: str
    thumbnail_url: Optional[str] = None
    title: Optional[str] = None
    domain: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class ImageSearchResult(BaseModel):
    """Image search result response."""
    candidates: list[ImageCandidate]
    total_found: int
    filtered: int
    query: str
