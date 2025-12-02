"""Auto-compose API router for variation generation."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
import asyncio
import httpx
import logging

logger = logging.getLogger(__name__)

from ..models.render_job import (
    RenderRequest, RenderSettings, ImageData, AudioData,
    OutputSettings, VibeType, AspectRatio, EffectPreset, ColorGrade, TextStyle,
    ScriptData, ScriptLine
)
from ..services.image_fetcher import ImageFetcher
from ..services.video_renderer import VideoRenderer
from ..utils.job_queue import JobQueue
from ..dependencies import get_job_queue, get_render_semaphore
from ..config import get_settings


router = APIRouter()


class ScriptLineInput(BaseModel):
    """Input format for script line from frontend."""
    text: str
    timing: float
    duration: float


class AutoComposeRequest(BaseModel):
    """Request for auto-compose with image search."""
    job_id: str = Field(..., description="Unique job identifier")
    search_query: str = Field(..., description="Main search query")
    search_tags: List[str] = Field(..., description="2-3 tags for image search")
    audio_url: Optional[str] = Field(default=None, description="Audio file URL")
    vibe: str = Field(default="Pop", description="Vibe preset")
    effect_preset: str = Field(default="zoom_beat", description="Effect preset (zoom_beat, crossfade, bounce, minimal)")
    color_grade: str = Field(default="vibrant", description="Color grading (vibrant, cinematic, bright, natural, moody)")
    text_style: str = Field(default="bold_pop", description="Text style (bold_pop, fade_in, slide_in, minimal, none)")
    aspect_ratio: str = Field(default="9:16", description="Output aspect ratio")
    target_duration: int = Field(default=15, description="Target duration in seconds")
    campaign_id: Optional[str] = Field(default=None, description="Campaign ID for S3 path")
    callback_url: Optional[str] = Field(default=None, description="URL to call when job completes")
    # Script lines for text overlays (subtitles/captions)
    script_lines: Optional[List[ScriptLineInput]] = Field(default=None, description="Script lines for text overlays")


class AutoComposeResponse(BaseModel):
    """Response for auto-compose request."""
    status: str
    job_id: str
    message: Optional[str] = None
    search_results: Optional[int] = None


async def send_callback(callback_url: str, job_id: str, status: str, output_url: Optional[str] = None, error: Optional[str] = None, progress: Optional[int] = None):
    """Send callback to notify job status changes."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "job_id": job_id,
                "status": status,
                "output_url": output_url,
                "error": error,
                "progress": progress,
            }
            response = await client.post(callback_url, json=payload)
            if response.status_code != 200:
                logger.error(f"Callback failed with status {response.status_code}: {response.text}")
            else:
                logger.info(f"Callback sent successfully for job {job_id}: status={status}")
    except Exception as e:
        logger.error(f"Failed to send callback for job {job_id}: {e}")


async def process_auto_compose(request: AutoComposeRequest, job_queue: Optional[JobQueue]):
    """Background task to process auto-compose job with concurrency control."""
    settings = get_settings()
    output_url = None
    final_status = "failed"
    error_message = None

    # Get render semaphore for concurrency control
    semaphore = get_render_semaphore()
    semaphore_acquired = False  # Track if we acquired the semaphore (for cleanup)

    try:
        # Wait for semaphore (limits concurrent renders)
        if semaphore:
            logger.info(f"[Auto-Compose] Job {request.job_id} waiting for render slot...")
            if job_queue:
                await job_queue.update_job(
                    request.job_id,
                    status="queued",
                    progress=0,
                    current_step="Waiting for render slot..."
                )
            # Send callback for "queued" status so frontend shows "대기중"
            if request.callback_url:
                await send_callback(request.callback_url, request.job_id, "queued", progress=0)
            await semaphore.acquire()
            semaphore_acquired = True
            logger.info(f"[Auto-Compose] Job {request.job_id} acquired render slot")

        # Update status to processing
        if job_queue:
            await job_queue.update_job(
                request.job_id,
                status="processing",
                progress=5,
                current_step="Searching images..."
            )
        # Send callback for "processing" status so frontend shows "처리중"
        if request.callback_url:
            await send_callback(request.callback_url, request.job_id, "processing", progress=5)

        # Search for images using the tags
        image_fetcher = ImageFetcher()

        # Try each tag combination until we get enough images
        # Use progressive resolution fallback: 720 -> 480 -> 360
        all_candidates = []
        min_resolutions = [720, 480, 360]

        for min_res in min_resolutions:
            if len(all_candidates) >= 3:
                break

            logger.info(f"[Auto-Compose] Job {request.job_id} searching with min_res={min_res}")

            for tag in request.search_tags:
                result = await image_fetcher.search(
                    query=tag,
                    max_results=10,
                    min_width=min_res,
                    min_height=min_res
                )
                all_candidates.extend(result.candidates)

            # Also try the full query
            full_result = await image_fetcher.search(
                query=request.search_query,
                max_results=10,
                min_width=min_res,
                min_height=min_res
            )
            all_candidates.extend(full_result.candidates)

        # Remove duplicates based on URL
        seen_urls = set()
        unique_candidates = []
        for candidate in all_candidates:
            if candidate.source_url not in seen_urls:
                seen_urls.add(candidate.source_url)
                unique_candidates.append(candidate)

        if len(unique_candidates) < 3:
            error_message = f"Not enough images found. Only {len(unique_candidates)} images."
            if job_queue:
                await job_queue.update_job(
                    request.job_id,
                    status="failed",
                    error=error_message
                )
            # Send callback for failure
            if request.callback_url:
                await send_callback(request.callback_url, request.job_id, "failed", error=error_message)
            return

        # Select images for the video (8-12 images typically)
        target_image_count = min(12, max(6, len(unique_candidates)))
        selected_images = unique_candidates[:target_image_count]

        if job_queue:
            await job_queue.update_job(
                request.job_id,
                progress=20,
                current_step=f"Found {len(selected_images)} images. Verifying accessibility..."
            )

        # Verify images are accessible (filter out 403/blocked URLs)
        verified_images = []
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            for img in selected_images:
                try:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "image/*,*/*;q=0.8",
                    }
                    resp = await client.head(img.source_url, headers=headers)
                    if resp.status_code < 400:
                        verified_images.append(img)
                    else:
                        logger.warning(f"[Auto-Compose] Image blocked ({resp.status_code}): {img.source_url[:80]}")
                except Exception as e:
                    logger.warning(f"[Auto-Compose] Image verification failed: {e}")
                    continue

        logger.info(f"[Auto-Compose] Verified {len(verified_images)}/{len(selected_images)} images accessible")

        # Check we still have enough images after filtering
        if len(verified_images) < 3:
            error_message = f"Not enough accessible images. Only {len(verified_images)} images passed verification."
            if job_queue:
                await job_queue.update_job(
                    request.job_id,
                    status="failed",
                    error=error_message
                )
            if request.callback_url:
                await send_callback(request.callback_url, request.job_id, "failed", error=error_message)
            return

        if job_queue:
            await job_queue.update_job(
                request.job_id,
                progress=30,
                current_step=f"Verified {len(verified_images)} images. Preparing render..."
            )

        # Prepare image data for rendering (only verified images)
        images = [
            ImageData(url=img.source_url, order=i)
            for i, img in enumerate(verified_images)
        ]

        # Map vibe string to enum
        vibe_map = {
            "Exciting": VibeType.EXCITING,
            "Emotional": VibeType.EMOTIONAL,
            "Pop": VibeType.POP,
            "Minimal": VibeType.MINIMAL,
        }
        vibe = vibe_map.get(request.vibe, VibeType.POP)

        # Map aspect ratio
        aspect_map = {
            "9:16": AspectRatio.PORTRAIT,
            "16:9": AspectRatio.LANDSCAPE,
            "1:1": AspectRatio.SQUARE,
        }
        aspect_ratio = aspect_map.get(request.aspect_ratio, AspectRatio.PORTRAIT)

        # Map effect preset
        effect_map = {
            "zoom_beat": EffectPreset.ZOOM_BEAT,
            "crossfade": EffectPreset.CROSSFADE,
            "bounce": EffectPreset.BOUNCE,
            "minimal": EffectPreset.MINIMAL,
        }
        effect_preset = effect_map.get(request.effect_preset, EffectPreset.ZOOM_BEAT)

        # Map color grade
        color_map = {
            "vibrant": ColorGrade.VIBRANT,
            "cinematic": ColorGrade.CINEMATIC,
            "bright": ColorGrade.BRIGHT,
            "natural": ColorGrade.NATURAL,
            "moody": ColorGrade.MOODY,
        }
        color_grade = color_map.get(request.color_grade, ColorGrade.VIBRANT)

        # Map text style
        text_map = {
            "bold_pop": TextStyle.BOLD_POP,
            "fade_in": TextStyle.FADE_IN,
            "slide_in": TextStyle.SLIDE_IN,
            "minimal": TextStyle.MINIMAL,
            "none": TextStyle.MINIMAL,  # "none" maps to minimal
        }
        text_style = text_map.get(request.text_style, TextStyle.BOLD_POP)

        logger.info(f"[Auto-Compose] Job {request.job_id} settings: vibe={vibe}, effect={effect_preset}, color={color_grade}, text={text_style}")

        # Validate audio URL is provided
        if not request.audio_url:
            error_message = "Audio URL is required for compose video generation"
            logger.error(f"[Auto-Compose] Job {request.job_id} failed: {error_message}")
            if job_queue:
                await job_queue.update_job(
                    request.job_id,
                    status="failed",
                    error=error_message
                )
            if request.callback_url:
                await send_callback(request.callback_url, request.job_id, "failed", error=error_message)
            return

        # Create render request
        s3_folder = request.campaign_id or "auto-compose"

        # Convert script_lines to ScriptData if provided
        script_data = None
        if request.script_lines:
            script_data = ScriptData(
                lines=[ScriptLine(text=sl.text, timing=sl.timing, duration=sl.duration)
                       for sl in request.script_lines]
            )
            logger.info(f"[Auto-Compose] Job {request.job_id} has {len(request.script_lines)} script lines for subtitles")

        render_request = RenderRequest(
            job_id=request.job_id,
            images=images,
            audio=AudioData(
                url=request.audio_url or "",
                start_time=0,
                duration=None
            ),
            script=script_data,
            settings=RenderSettings(
                vibe=vibe,
                effect_preset=effect_preset,
                aspect_ratio=aspect_ratio,
                target_duration=request.target_duration,
                color_grade=color_grade,
                text_style=text_style,
            ),
            output=OutputSettings(
                s3_bucket=settings.aws_s3_bucket,
                s3_key=f"compose/{s3_folder}/{request.job_id}.mp4"
            )
        )

        # Render the video
        if job_queue:
            await job_queue.update_job(
                request.job_id,
                progress=40,
                current_step="Rendering video..."
            )

        renderer = VideoRenderer()

        async def progress_callback(job_id: str, progress: int, step: str):
            if job_queue:
                # Map renderer progress (0-100) to overall progress (40-100)
                overall_progress = 40 + int(progress * 0.6)
                await job_queue.update_job(job_id, progress=overall_progress, current_step=step)

        output_url = await renderer.render(render_request, progress_callback)
        final_status = "completed"

        # Update completion
        if job_queue:
            await job_queue.update_job(
                request.job_id,
                status="completed",
                progress=100,
                current_step="Completed",
                output_url=output_url,
                metadata={
                    "search_tags": request.search_tags,
                    "vibe": request.vibe,
                    "effect_preset": request.effect_preset,
                    "color_grade": request.color_grade,
                    "text_style": request.text_style,
                    "image_count": len(selected_images),
                }
            )

        # Send success callback
        if request.callback_url:
            await send_callback(request.callback_url, request.job_id, "completed", output_url=output_url)

    except Exception as e:
        error_message = str(e)
        logger.error(f"[Auto-Compose] Job {request.job_id} failed: {error_message}")
        if job_queue:
            await job_queue.update_job(
                request.job_id,
                status="failed",
                error=error_message
            )

        # Send failure callback
        if request.callback_url:
            await send_callback(request.callback_url, request.job_id, "failed", error=error_message)

    finally:
        # Release semaphore only if we acquired it
        if semaphore_acquired and semaphore:
            semaphore.release()
            logger.info(f"[Auto-Compose] Job {request.job_id} released render slot")


@router.post("/auto", response_model=AutoComposeResponse)
async def auto_compose(request: AutoComposeRequest):
    """
    Auto-compose: Search images by tags and create a slideshow video.

    This endpoint is designed for creating variations of existing compose videos:
    - Takes 2-3 search tags (extracted from original prompt)
    - Searches for new images
    - Creates a new slideshow with the specified vibe

    Jobs run in parallel up to max_concurrent_jobs (default: 2).
    """
    job_queue = get_job_queue()

    if job_queue:
        await job_queue.create_job(request.job_id, request.model_dump())

    # Start background processing with asyncio.create_task for true parallel execution
    asyncio.create_task(process_auto_compose(request, job_queue))

    return AutoComposeResponse(
        status="accepted",
        job_id=request.job_id,
        message=f"Auto-compose job started with tags: {', '.join(request.search_tags)}"
    )


@router.post("/auto/sync", response_model=dict)
async def auto_compose_sync(request: AutoComposeRequest):
    """
    Synchronous auto-compose (for testing).
    Blocks until complete.
    """
    job_queue = get_job_queue()

    if job_queue:
        await job_queue.create_job(request.job_id, request.model_dump())

    await process_auto_compose(request, job_queue)

    if job_queue:
        job = await job_queue.get_job(request.job_id)
        if job:
            return {
                "status": job.get("status", "unknown"),
                "job_id": request.job_id,
                "output_url": job.get("output_url"),
                "error": job.get("error"),
            }

    return {
        "status": "completed",
        "job_id": request.job_id,
    }
