"""Pop vibe preset - trendy, medium-paced content."""

from .base import VibePreset


POP_PRESET = VibePreset(
    name="Pop",
    bpm_range=(100, 120),
    cut_style="medium",
    base_cut_duration=3.0,  # Natural conversational pace (was 1.0)
    transition_type="bounce",
    transition_duration=0.25,
    motion_style="zoom_out",
    color_grade="bright",
    text_style="slide_in",
    effects=["color_pop", "soft_glow"],
    duration_range=(15, 20)  # Trendy: balanced duration
)
