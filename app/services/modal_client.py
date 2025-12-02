"""
Modal Client for calling remote render functions.

This client provides an interface to call Modal serverless functions
for GPU-accelerated video rendering from the FastAPI backend.
"""

import os
import httpx
import logging
from typing import Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ModalJobStatus(str, Enum):
    """Status of a Modal render job."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"


@dataclass
class ModalJobResult:
    """Result of a Modal render job."""
    status: ModalJobStatus
    call_id: Optional[str] = None
    job_id: Optional[str] = None
    output_url: Optional[str] = None
    error: Optional[str] = None
    progress: int = 0


class ModalClient:
    """
    Client for interacting with Modal serverless functions.

    Usage:
        client = ModalClient()

        # Submit a render job
        result = await client.submit_render(request_data, use_gpu=True)
        call_id = result.call_id

        # Poll for status
        status = await client.get_status(call_id)
        if status.status == ModalJobStatus.COMPLETED:
            print(f"Video URL: {status.output_url}")
    """

    def __init__(
        self,
        submit_url: Optional[str] = None,
        status_url: Optional[str] = None
    ):
        """
        Initialize the Modal client.

        Args:
            submit_url: URL for submit_render endpoint
            status_url: URL for get_render_status endpoint

        Environment variables:
            MODAL_SUBMIT_URL: URL for submit_render endpoint
            MODAL_STATUS_URL: URL for get_render_status endpoint
            MODAL_WEBHOOK_URL: Legacy - base URL (deprecated)
        """
        # Support separate URLs for each endpoint (Modal's default)
        self.submit_url = submit_url or os.getenv(
            "MODAL_SUBMIT_URL",
            os.getenv("MODAL_WEBHOOK_URL", "https://modawnai--hydra-compose-engine-submit-render.modal.run")
        )
        self.status_url = status_url or os.getenv(
            "MODAL_STATUS_URL",
            "https://modawnai--hydra-compose-engine-get-render-status.modal.run"
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def submit_render(
        self,
        request_data: dict,
        use_gpu: bool = True
    ) -> ModalJobResult:
        """
        Submit a render job to Modal.

        Args:
            request_data: RenderRequest data as dict
            use_gpu: Whether to use GPU acceleration (default: True)

        Returns:
            ModalJobResult with call_id for polling
        """
        try:
            client = await self._get_client()

            # Add GPU preference to request
            payload = {**request_data, "use_gpu": use_gpu}

            response = await client.post(
                self.submit_url,
                json=payload,
            )
            response.raise_for_status()

            data = response.json()
            logger.info(f"Modal job submitted: {data.get('call_id')} (GPU: {use_gpu})")

            return ModalJobResult(
                status=ModalJobStatus.QUEUED,
                call_id=data.get("call_id"),
                job_id=data.get("job_id"),
            )

        except httpx.HTTPError as e:
            logger.error(f"Failed to submit Modal job: {e}")
            return ModalJobResult(
                status=ModalJobStatus.ERROR,
                error=str(e),
                job_id=request_data.get("job_id"),
            )

    async def get_status(self, call_id: str) -> ModalJobResult:
        """
        Get the status of a Modal render job.

        Args:
            call_id: The Modal call ID from submit_render

        Returns:
            ModalJobResult with current status
        """
        try:
            client = await self._get_client()

            response = await client.get(
                self.status_url,
                params={"call_id": call_id},
            )

            # 202 means still processing
            if response.status_code == 202:
                return ModalJobResult(
                    status=ModalJobStatus.PROCESSING,
                    call_id=call_id,
                )

            response.raise_for_status()
            data = response.json()

            status_str = data.get("status", "error")
            result = data.get("result", {})

            return ModalJobResult(
                status=ModalJobStatus(status_str),
                call_id=call_id,
                job_id=result.get("job_id"),
                output_url=result.get("output_url"),
                error=result.get("error") or data.get("error"),
            )

        except httpx.HTTPError as e:
            logger.error(f"Failed to get Modal job status: {e}")
            return ModalJobResult(
                status=ModalJobStatus.ERROR,
                call_id=call_id,
                error=str(e),
            )

    async def render_sync(
        self,
        request_data: dict,
        use_gpu: bool = True,
        poll_interval: float = 2.0,
        timeout: float = 600.0
    ) -> ModalJobResult:
        """
        Submit a render job and wait for completion.

        Args:
            request_data: RenderRequest data as dict
            use_gpu: Whether to use GPU acceleration
            poll_interval: Seconds between status polls
            timeout: Maximum time to wait in seconds

        Returns:
            ModalJobResult with final status
        """
        import asyncio

        # Submit the job
        submit_result = await self.submit_render(request_data, use_gpu)
        if submit_result.status == ModalJobStatus.ERROR:
            return submit_result

        call_id = submit_result.call_id
        elapsed = 0.0

        # Poll for completion
        while elapsed < timeout:
            status = await self.get_status(call_id)

            if status.status in (ModalJobStatus.COMPLETED, ModalJobStatus.FAILED, ModalJobStatus.ERROR):
                return status

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        # Timeout
        return ModalJobResult(
            status=ModalJobStatus.ERROR,
            call_id=call_id,
            error=f"Timeout after {timeout} seconds",
        )


# Singleton instance
_modal_client: Optional[ModalClient] = None


def get_modal_client() -> ModalClient:
    """Get the singleton Modal client instance."""
    global _modal_client
    if _modal_client is None:
        _modal_client = ModalClient()
    return _modal_client


async def close_modal_client():
    """Close the Modal client (call on shutdown)."""
    global _modal_client
    if _modal_client:
        await _modal_client.close()
        _modal_client = None
