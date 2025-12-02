"""
RunPod Serverless Handler for Video Rendering with GPU Acceleration (NVENC).

This handler receives render requests and processes videos using NVIDIA GPU.

Deploy:
  1. Build: docker build -t hydra-compose-engine .
  2. Push to Docker Hub or RunPod registry
  3. Create endpoint on RunPod with this image

Environment Variables (set in RunPod endpoint):
  - AWS_ACCESS_KEY_ID
  - AWS_SECRET_ACCESS_KEY
  - AWS_REGION (default: ap-southeast-2)
  - AWS_S3_BUCKET (default: hydra-assets-hybe)
"""

import runpod
import asyncio
import traceback
import logging
import sys
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Add app to path
sys.path.insert(0, "/")


def check_nvenc_available() -> bool:
    """Check if NVENC hardware encoding is available."""
    import subprocess
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return "h264_nvenc" in result.stdout
    except Exception as e:
        logger.warning(f"NVENC check failed: {e}")
        return False


def handler(job: dict) -> dict:
    """
    RunPod handler function for video rendering.

    Input (job["input"]):
        Same as Modal RenderRequest:
        - job_id: str
        - images: list[{url, order}]
        - audio: {url, start_time?, duration?}
        - script?: {lines: [{text, timing, duration}]}
        - settings: {vibe, effect_preset, aspect_ratio, target_duration, text_style, color_grade}
        - output: {s3_bucket, s3_key}
        - use_gpu: bool (default True)

    Returns:
        {status, job_id, output_url, error?}
    """
    job_input = job["input"]
    job_id = job_input.get("job_id", "unknown")
    use_gpu = job_input.pop("use_gpu", True)

    logger.info(f"[{job_id}] === Starting RunPod GPU render ===")
    logger.info(f"[{job_id}] Images: {len(job_input.get('images', []))}")
    logger.info(f"[{job_id}] Use GPU (NVENC): {use_gpu}")

    # Check NVENC availability
    nvenc_available = check_nvenc_available()
    logger.info(f"[{job_id}] NVENC available: {nvenc_available}")

    # Set encoding mode based on availability
    os.environ["USE_NVENC"] = "1" if (use_gpu and nvenc_available) else "0"

    try:
        from app.models.render_job import RenderRequest
        from app.services.video_renderer import VideoRenderer

        # Parse request
        request = RenderRequest(**job_input)

        logger.info(f"[{job_id}] Vibe: {request.settings.vibe.value}")
        logger.info(f"[{job_id}] Aspect Ratio: {request.settings.aspect_ratio.value}")
        logger.info(f"[{job_id}] Target Duration: {request.settings.target_duration}s")

        # Create renderer
        renderer = VideoRenderer()

        # Progress callback
        async def progress_callback(job_id: str, progress: int, step: str):
            logger.info(f"[{job_id}] [{progress:3d}%] {step}")
            # RunPod supports streaming progress updates
            runpod.serverless.progress_update(job, progress / 100)

        # Run async render
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            output_url = loop.run_until_complete(
                renderer.render(request, progress_callback)
            )
        finally:
            loop.close()

        logger.info(f"[{job_id}] === Render complete ===")
        logger.info(f"[{job_id}] Output: {output_url}")

        return {
            "status": "completed",
            "job_id": job_id,
            "output_url": output_url,
            "nvenc_used": use_gpu and nvenc_available,
            "error": None,
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"[{job_id}] === Render FAILED ===")
        logger.error(f"[{job_id}] Error: {error_msg}")
        logger.error(f"[{job_id}] Traceback:\n{traceback.format_exc()}")

        return {
            "status": "failed",
            "job_id": job_id,
            "output_url": None,
            "error": error_msg,
        }


# RunPod serverless entrypoint
if __name__ == "__main__":
    logger.info("Starting Hydra Compose Engine (RunPod Serverless)")
    logger.info(f"NVENC available: {check_nvenc_available()}")

    runpod.serverless.start({
        "handler": handler
    })
