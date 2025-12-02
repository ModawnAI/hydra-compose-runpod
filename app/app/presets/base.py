"""Base preset class for vibe configurations."""

from dataclasses import dataclass, field
from typing import Literal, Tuple


@dataclass
class VibePreset:
    """Configuration preset for a video vibe/mood.

    TikTok-optimized with duration ranges (10-30 seconds).
    """

    name: str
    bpm_range: tuple[int, int]
    cut_style: Literal["fast", "medium", "slow"]
    base_cut_duration: float  # seconds per image
    transition_type: Literal["zoom_beat", "crossfade", "bounce", "slide", "cut"]
    transition_duration: float
    motion_style: Literal["zoom_in", "zoom_out", "pan", "static"]
    color_grade: Literal["vibrant", "cinematic", "bright", "natural", "bw"]
    text_style: Literal["bold_pop", "fade_in", "slide_in", "minimal"]
    effects: list[str]

    # TikTok duration range (min, max) in seconds
    duration_range: Tuple[int, int] = field(default=(15, 25))
