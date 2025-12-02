"""Audio analysis API router."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..services.audio_analyzer import AudioAnalyzer
from ..models.responses import AudioAnalysis
from ..utils.s3_client import S3Client
from ..utils.temp_files import TempFileManager


router = APIRouter()


class AudioAnalyzeRequest(BaseModel):
    """Request model for audio analysis."""
    audio_url: str
    job_id: Optional[str] = "temp"


class BestSegmentRequest(BaseModel):
    """Request model for finding best audio segment."""
    audio_url: str
    target_duration: float = 15.0
    job_id: Optional[str] = "temp"


class BestSegmentResponse(BaseModel):
    """Response model for best segment."""
    start_time: float
    end_time: float
    duration: float


@router.post("/analyze", response_model=AudioAnalysis)
async def analyze_audio(request: AudioAnalyzeRequest):
    """
    Analyze an audio file for BPM, beats, and energy.
    """
    s3 = S3Client()
    temp = TempFileManager()
    analyzer = AudioAnalyzer()

    # Download audio to temp
    local_path = temp.get_path(request.job_id, "audio_analyze.mp3")

    try:
        await s3.download_file(request.audio_url, local_path)
        result = analyzer.analyze(local_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        # Cleanup
        import os
        if os.path.exists(local_path):
            os.remove(local_path)


@router.post("/best-segment", response_model=BestSegmentResponse)
async def find_best_segment(request: BestSegmentRequest):
    """
    Find the best segment of audio for a target duration.
    Returns the highest-energy segment.
    """
    s3 = S3Client()
    temp = TempFileManager()
    analyzer = AudioAnalyzer()

    local_path = temp.get_path(request.job_id, "audio_segment.mp3")

    try:
        await s3.download_file(request.audio_url, local_path)
        start, end = analyzer.find_best_segment(local_path, request.target_duration)

        return BestSegmentResponse(
            start_time=start,
            end_time=end,
            duration=end - start
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Segment analysis failed: {str(e)}")
    finally:
        import os
        if os.path.exists(local_path):
            os.remove(local_path)
