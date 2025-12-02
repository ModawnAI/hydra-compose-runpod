"""Job status API router."""

from fastapi import APIRouter, HTTPException

from ..models.responses import JobStatusResponse
from ..dependencies import get_job_queue


router = APIRouter()


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get the status of a render job.
    """
    job_queue = get_job_queue()

    if not job_queue:
        raise HTTPException(status_code=503, detail="Job queue not available")

    status = await job_queue.get_job_status(job_id)

    if not status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return status


@router.delete("/{job_id}")
async def cancel_job(job_id: str):
    """
    Cancel/delete a render job.
    Note: This only removes the job record, not the actual process if running.
    """
    job_queue = get_job_queue()

    if not job_queue:
        raise HTTPException(status_code=503, detail="Job queue not available")

    await job_queue.delete_job(job_id)

    return {"status": "deleted", "job_id": job_id}
