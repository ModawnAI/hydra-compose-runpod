"""Image search API router."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..services.image_fetcher import ImageFetcher
from ..models.responses import ImageSearchResult


router = APIRouter()


class ImageSearchRequest(BaseModel):
    """Request model for image search."""
    query: str
    max_results: int = 20
    min_width: int = 720
    min_height: int = 720
    safe_search: str = "active"


@router.post("/search", response_model=ImageSearchResult)
async def search_images(request: ImageSearchRequest):
    """
    Search for images using Google Custom Search API.
    """
    fetcher = ImageFetcher()

    result = await fetcher.search(
        query=request.query,
        max_results=request.max_results,
        min_width=request.min_width,
        min_height=request.min_height,
        safe_search=request.safe_search
    )

    return result


class ImageDownloadRequest(BaseModel):
    """Request model for image download."""
    url: str
    job_id: str
    filename: str


class ImageDownloadResponse(BaseModel):
    """Response model for image download."""
    success: bool
    local_path: Optional[str] = None
    error: Optional[str] = None


@router.post("/download", response_model=ImageDownloadResponse)
async def download_image(request: ImageDownloadRequest):
    """
    Download an image from URL.
    """
    from ..utils.temp_files import TempFileManager

    temp = TempFileManager()
    output_path = temp.get_path(request.job_id, request.filename)

    fetcher = ImageFetcher()
    result = await fetcher.download_image(request.url, output_path)

    if result:
        return ImageDownloadResponse(success=True, local_path=result)
    else:
        return ImageDownloadResponse(success=False, error="Failed to download image")
