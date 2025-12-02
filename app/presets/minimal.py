"""Minimal vibe preset - clean, simple content."""

from .base import VibePreset


MINIMAL_PRESET = VibePreset(
    name="Minimal",
    bpm_range=(80, 120),
    cut_style="medium",
    base_cut_duration=3.5,  # Clean, unhurried pace (was 1.5)
    transition_type="cut",
    transition_duration=0.0,
    motion_style="static",
    color_grade="natural",
    text_style="minimal",
    effects=[],
    duration_range=(15, 25)  # Clean: flexible duration
)
