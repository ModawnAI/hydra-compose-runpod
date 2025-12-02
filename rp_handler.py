"""
RunPod Serverless Handler for Video Rendering with GPU Acceleration (NVENC).

This handler receives render requests and processes videos using NVIDIA GPU.

Deploy:
  1. Build Docker image
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
import concurrent.futures

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


def run_async_render(job_input: dict, use_nvenc: bool) -> str:
    """
    Run the async render in a completely separate thread with its own event loop.
    This avoids conflicts with RunPod's event loop.
    """
    job_id = job_input.get("job_id", "unknown")

    # Set encoding mode
    os.environ["USE_NVENC"] = "1" if use_nvenc else "0"

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

    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        output_url = loop.run_until_complete(
            renderer.render(request, progress_callback)
        )
        return output_url
    finally:
        loop.close()


def handler(job: dict) -> dict:
    """
    RunPod handler function for video rendering.

    Input (job["input"]):
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
    job_input = job["input"].copy()  # Copy to avoid modifying original
    job_id = job_input.get("job_id", "unknown")
    use_gpu = job_input.pop("use_gpu", True)

    logger.info(f"[{job_id}] === Starting RunPod GPU render ===")
    logger.info(f"[{job_id}] Images: {len(job_input.get('images', []))}")
    logger.info(f"[{job_id}] Use GPU (NVENC): {use_gpu}")

    # Check NVENC availability
    nvenc_available = check_nvenc_available()
    logger.info(f"[{job_id}] NVENC available: {nvenc_available}")

    use_nvenc = use_gpu and nvenc_available

    try:
        # Run the async render in a separate thread with its own event loop
        # This completely isolates it from RunPod's event loop
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_async_render, job_input, use_nvenc)
            output_url = future.result(timeout=600)  # 10 minute timeout

        logger.info(f"[{job_id}] === Render complete ===")
        logger.info(f"[{job_id}] Output: {output_url}")

        return {
            "status": "completed",
            "job_id": job_id,
            "output_url": output_url,
            "nvenc_used": use_nvenc,
            "error": None,
        }

    except concurrent.futures.TimeoutError:
        error_msg = "Render timed out after 10 minutes"
        logger.error(f"[{job_id}] === Render TIMEOUT ===")
        return {
            "error": error_msg,
            "status": "failed",
            "job_id": job_id,
            "output_url": None,
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"[{job_id}] === Render FAILED ===")
        logger.error(f"[{job_id}] Error: {error_msg}")
        logger.error(f"[{job_id}] Traceback:\n{traceback.format_exc()}")

        # Return error in RunPod's expected format
        return {
            "error": error_msg,
            "status": "failed",
            "job_id": job_id,
            "output_url": None,
        }


# RunPod serverless entrypoint
if __name__ == "__main__":
    logger.info("Starting Hydra Compose Engine (RunPod Serverless)")
    logger.info(f"NVENC available: {check_nvenc_available()}")

    runpod.serverless.start({"handler": handler})
