"""Exciting vibe preset - energetic, fast-paced content."""

from .base import VibePreset


EXCITING_PRESET = VibePreset(
    name="Exciting",
    bpm_range=(120, 140),
    cut_style="fast",
    base_cut_duration=2.5,  # Dynamic but not overwhelming (was 0.5)
    transition_type="zoom_beat",
    transition_duration=0.15,
    motion_style="zoom_in",
    color_grade="vibrant",
    text_style="bold_pop",
    effects=["shake_on_beat", "flash_transition", "glow"],
    duration_range=(10, 15)  # Fast-paced: shorter videos
)
