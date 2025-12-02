"""Configuration module for compose engine."""

import os
import tempfile
from pydantic_settings import BaseSettings
from functools import lru_cache

from .tiktok_optimization import (
    DURATION_RANGES,
    MIN_VIDEO_DURATION,
    MAX_VIDEO_DURATION,
    TIKTOK_OPTIMAL_DURATION,
    HOOK_CONFIG,
    TEXT_CONFIG,
    AUDIO_CONFIG,
    ENGAGEMENT_CONFIG,
    CONTENT_STRUCTURES,
    VIBE_OVERRIDES,
    get_optimal_duration,
    get_images_for_duration,
    calculate_text_timing,
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Service info
    app_name: str = "Compose Engine"
    app_version: str = "1.0.0"
    debug: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/1"

    # AWS S3
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-southeast-2"
    aws_s3_bucket: str = "hydra-assets-hybe"

    # Google Custom Search
    google_search_api_key: str = ""
    google_search_cx: str = ""

    # Temp directory for rendering (platform-aware default)
    temp_dir: str = os.path.join(tempfile.gettempdir(), "compose")

    # Rendering settings
    max_concurrent_jobs: int = 4
    default_fps: int = 30
    default_video_codec: str = "libx264"
    default_audio_codec: str = "aac"

    # Modal serverless settings
    modal_enabled: bool = False  # Set to True to enable Modal cloud rendering
    modal_submit_url: str = ""   # Modal submit_render endpoint URL
    modal_status_url: str = ""   # Modal get_render_status endpoint URL
    modal_use_gpu: bool = True   # Use GPU acceleration by default

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra env vars from parent project


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


__all__ = [
    # Settings
    "Settings",
    "get_settings",
    # TikTok optimization
    "DURATION_RANGES",
    "MIN_VIDEO_DURATION",
    "MAX_VIDEO_DURATION",
    "TIKTOK_OPTIMAL_DURATION",
    "HOOK_CONFIG",
    "TEXT_CONFIG",
    "AUDIO_CONFIG",
    "ENGAGEMENT_CONFIG",
    "CONTENT_STRUCTURES",
    "VIBE_OVERRIDES",
    "get_optimal_duration",
    "get_images_for_duration",
    "calculate_text_timing",
]
