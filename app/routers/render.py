"""Render API router."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
import asyncio
import logging

from ..models.render_job import RenderRequest, RenderResponse
from ..models.responses import JobStatus
from ..services.video_renderer import VideoRenderer
from ..utils.job_queue import JobQueue, create_progress_callback
from ..dependencies import get_job_queue
from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


async def process_render_job(request: RenderRequest, job_queue: JobQueue):
    """Background task to process a render job."""
    try:
        # Update status to processing
        await job_queue.update_job(
            request.job_id,
            status=JobStatus.PROCESSING,
            progress=0,
            current_step="Starting render"
        )

        # Create progress callback
        async def progress_callback(job_id: str, progress: int, step: str):
            await job_queue.update_job(
                job_id,
                progress=progress,
                current_step=step
            )

        # Create renderer and process
        renderer = VideoRenderer()
        output_url = await renderer.render(request, progress_callback)

        # Update with completion
        await job_queue.update_job(
            request.job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            current_step="Completed",
            output_url=output_url
        )

    except Exception as e:
        # Update with error
        await job_queue.update_job(
            request.job_id,
            status=JobStatus.FAILED,
            error=str(e)
        )


@router.post("", response_model=RenderResponse)
async def start_render(
    request: RenderRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a video rendering job.
    The job runs in the background and status can be polled via /job/{job_id}/status.
    """
    job_queue = get_job_queue()

    if not job_queue:
        raise HTTPException(status_code=503, detail="Job queue not available")

    # Create job entry
    await job_queue.create_job(request.job_id, request.model_dump())

    # Add background task
    background_tasks.add_task(process_render_job, request, job_queue)

    return RenderResponse(
        status="accepted",
        job_id=request.job_id,
        message="Render job queued successfully"
    )


@router.post("/sync", response_model=dict)
async def render_sync(request: RenderRequest):
    """
    Synchronous rendering (for testing).
    Blocks until render is complete.
    """
    job_queue = get_job_queue()

    if job_queue:
        await job_queue.create_job(request.job_id, request.model_dump())

    renderer = VideoRenderer()

    async def progress_callback(job_id: str, progress: int, step: str):
        if job_queue:
            await job_queue.update_job(job_id, progress=progress, current_step=step)
        print(f"[{progress}%] {step}")

    try:
        output_url = await renderer.render(request, progress_callback)
        return {
            "status": "completed",
            "job_id": request.job_id,
            "output_url": output_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Modal (Serverless GPU) Rendering Endpoints
# ============================================================================

async def process_modal_render_job(request: RenderRequest, job_queue: JobQueue, use_gpu: bool = True):
    """Background task to process a render job via Modal."""
    from ..services.modal_client import get_modal_client, ModalJobStatus

    job_id = request.job_id
    modal_client = get_modal_client()

    try:
        # Update status to processing
        await job_queue.update_job(
            job_id,
            status=JobStatus.PROCESSING,
            progress=0,
            current_step="Submitting to Modal cloud"
        )

        # Submit to Modal
        submit_result = await modal_client.submit_render(
            request.model_dump(),
            use_gpu=use_gpu
        )

        if submit_result.status == ModalJobStatus.ERROR:
            await job_queue.update_job(
                job_id,
                status=JobStatus.FAILED,
                error=submit_result.error or "Failed to submit to Modal"
            )
            return

        call_id = submit_result.call_id
        logger.info(f"[{job_id}] Modal job submitted: {call_id}")

        # Store Modal call_id in metadata for status polling
        await job_queue.update_job(
            job_id,
            progress=5,
            current_step="Processing on Modal cloud",
            metadata={"modal_call_id": call_id, "use_gpu": use_gpu}
        )

        # Poll for completion
        poll_interval = 3.0
        max_polls = 200  # ~10 minutes max
        polls = 0

        while polls < max_polls:
            status = await modal_client.get_status(call_id)

            if status.status == ModalJobStatus.COMPLETED:
                await job_queue.update_job(
                    job_id,
                    status=JobStatus.COMPLETED,
                    progress=100,
                    current_step="Completed",
                    output_url=status.output_url
                )
                logger.info(f"[{job_id}] Modal render completed: {status.output_url}")
                return

            elif status.status == ModalJobStatus.FAILED:
                await job_queue.update_job(
                    job_id,
                    status=JobStatus.FAILED,
                    error=status.error or "Modal render failed"
                )
                logger.error(f"[{job_id}] Modal render failed: {status.error}")
                return

            elif status.status == ModalJobStatus.ERROR:
                await job_queue.update_job(
                    job_id,
                    status=JobStatus.FAILED,
                    error=status.error or "Modal error"
                )
                return

            # Still processing - update progress estimate
            progress = min(90, 5 + (polls * 85 // max_polls))
            await job_queue.update_job(
                job_id,
                progress=progress,
                current_step="Rendering on Modal cloud (GPU)" if use_gpu else "Rendering on Modal cloud (CPU)"
            )

            await asyncio.sleep(poll_interval)
            polls += 1

        # Timeout
        await job_queue.update_job(
            job_id,
            status=JobStatus.FAILED,
            error="Modal render timed out"
        )

    except Exception as e:
        logger.error(f"[{job_id}] Modal render error: {e}")
        await job_queue.update_job(
            job_id,
            status=JobStatus.FAILED,
            error=str(e)
        )


@router.post("/modal", response_model=RenderResponse)
async def start_modal_render(
    request: RenderRequest,
    background_tasks: BackgroundTasks,
    use_gpu: bool = Query(default=True, description="Use GPU acceleration")
):
    """
    Start a video rendering job on Modal serverless cloud.

    - GPU mode (default): Uses NVIDIA T4 with NVENC for 5-10x faster encoding
    - CPU mode: Uses parallel CPU workers, more cost-effective for simple videos

    The job runs in the background and status can be polled via /job/{job_id}/status.
    """
    settings = get_settings()

    if not settings.modal_enabled:
        raise HTTPException(
            status_code=503,
            detail="Modal rendering is not enabled. Set MODAL_ENABLED=true"
        )

    job_queue = get_job_queue()
    if not job_queue:
        raise HTTPException(status_code=503, detail="Job queue not available")

    # Create job entry
    await job_queue.create_job(request.job_id, request.model_dump())

    # Add background task for Modal rendering
    background_tasks.add_task(process_modal_render_job, request, job_queue, use_gpu)

    return RenderResponse(
        status="accepted",
        job_id=request.job_id,
        message=f"Render job queued for Modal cloud (GPU: {use_gpu})"
    )


@router.post("/auto", response_model=RenderResponse)
async def start_auto_render(
    request: RenderRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a video rendering job with automatic backend selection.

    - If Modal is enabled and configured, uses Modal serverless GPU
    - Otherwise, falls back to local rendering

    The job runs in the background and status can be polled via /job/{job_id}/status.
    """
    settings = get_settings()
    job_queue = get_job_queue()

    if not job_queue:
        raise HTTPException(status_code=503, detail="Job queue not available")

    # Create job entry
    await job_queue.create_job(request.job_id, request.model_dump())

    # Choose rendering backend
    if settings.modal_enabled and settings.modal_submit_url:
        logger.info(f"[{request.job_id}] Using Modal cloud rendering")
        background_tasks.add_task(process_modal_render_job, request, job_queue, True)
        message = "Render job queued for Modal cloud (GPU)"
    else:
        logger.info(f"[{request.job_id}] Using local rendering")
        background_tasks.add_task(process_render_job, request, job_queue)
        message = "Render job queued for local rendering"

    return RenderResponse(
        status="accepted",
        job_id=request.job_id,
        message=message
    )
