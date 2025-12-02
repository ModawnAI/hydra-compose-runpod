"""Pydantic models for render job requests."""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class VibeType(str, Enum):
    """Vibe types for video composition."""
    EXCITING = "Exciting"
    EMOTIONAL = "Emotional"
    POP = "Pop"
    MINIMAL = "Minimal"


class EffectPreset(str, Enum):
    """Effect preset types."""
    ZOOM_BEAT = "zoom_beat"
    CROSSFADE = "crossfade"
    BOUNCE = "bounce"
    MINIMAL = "minimal"


class AspectRatio(str, Enum):
    """Supported aspect ratios."""
    PORTRAIT = "9:16"
    LANDSCAPE = "16:9"
    SQUARE = "1:1"


class TextStyle(str, Enum):
    """Text overlay styles."""
    BOLD_POP = "bold_pop"
    FADE_IN = "fade_in"
    SLIDE_IN = "slide_in"
    MINIMAL = "minimal"


class ColorGrade(str, Enum):
    """Color grading options."""
    VIBRANT = "vibrant"
    CINEMATIC = "cinematic"
    BRIGHT = "bright"
    NATURAL = "natural"
    MOODY = "moody"


class ImageData(BaseModel):
    """Image data for rendering."""
    url: str = Field(..., description="S3 URL of the image")
    order: int = Field(..., description="Order in the sequence")


class AudioData(BaseModel):
    """Audio data for rendering."""
    url: str = Field(..., description="S3 URL of the audio file")
    start_time: float = Field(default=0, description="Start time in seconds")
    duration: Optional[float] = Field(default=None, description="Duration to use")


class ScriptLine(BaseModel):
    """A single line of script text."""
    text: str = Field(..., description="Text content")
    timing: float = Field(..., description="Start time in seconds")
    duration: float = Field(default=3, description="Display duration")


class ScriptData(BaseModel):
    """Script data for text overlays."""
    lines: list[ScriptLine] = Field(default=[], description="Script lines")


class RenderSettings(BaseModel):
    """Settings for video rendering."""
    vibe: VibeType = Field(default=VibeType.POP, description="Vibe preset")
    effect_preset: EffectPreset = Field(
        default=EffectPreset.ZOOM_BEAT,
        description="Effect preset"
    )
    aspect_ratio: AspectRatio = Field(
        default=AspectRatio.PORTRAIT,
        description="Output aspect ratio"
    )
    target_duration: int = Field(
        default=15,
        description="Target video duration in seconds"
    )
    text_style: TextStyle = Field(
        default=TextStyle.BOLD_POP,
        description="Text overlay style"
    )
    color_grade: ColorGrade = Field(
        default=ColorGrade.VIBRANT,
        description="Color grading"
    )


class OutputSettings(BaseModel):
    """Output settings for rendered video."""
    s3_bucket: str = Field(..., description="S3 bucket name")
    s3_key: str = Field(..., description="S3 key for output file")


class RenderRequest(BaseModel):
    """Request model for video rendering."""
    job_id: str = Field(..., description="Unique job identifier")
    images: list[ImageData] = Field(..., description="Images to compose")
    audio: AudioData = Field(..., description="Audio track")
    script: Optional[ScriptData] = Field(default=None, description="Text overlays")
    settings: RenderSettings = Field(
        default_factory=RenderSettings,
        description="Render settings"
    )
    output: OutputSettings = Field(..., description="Output settings")


class RenderResponse(BaseModel):
    """Response model for render request."""
    status: str = Field(..., description="Job status")
    job_id: str = Field(..., description="Job identifier")
    message: Optional[str] = Field(default=None, description="Status message")
