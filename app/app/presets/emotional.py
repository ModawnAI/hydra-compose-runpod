"""Emotional vibe preset - slow, cinematic content."""

from .base import VibePreset


EMOTIONAL_PRESET = VibePreset(
    name="Emotional",
    bpm_range=(60, 80),
    cut_style="slow",
    base_cut_duration=4.5,  # Cinematic, breathing cuts (was 2.5)
    transition_type="crossfade",
    transition_duration=1.0,
    motion_style="pan",
    color_grade="cinematic",
    text_style="fade_in",
    effects=["film_grain", "vignette", "slight_desaturate"],
    duration_range=(20, 30)  # Cinematic: longer storytelling
)
