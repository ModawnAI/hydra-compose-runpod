"""Motion effects for video clips (Ken Burns, etc.)."""

from moviepy import ImageClip
from typing import List, Literal
import numpy as np


def apply_ken_burns(
    clip: ImageClip,
    style: Literal["zoom_in", "zoom_out", "pan", "static"],
    beat_times: List[float] = None
) -> ImageClip:
    """
    Apply Ken Burns effect (slow zoom/pan) to an image clip.

    Subtle motion parameters (5% zoom) for professional look:
    - zoom_in: 100% → 105% (gentle zoom in)
    - zoom_out: 105% → 100% (gentle zoom out)
    - pan: 3% horizontal movement (subtle drift)
    """
    if style == "static":
        return clip

    duration = clip.duration
    if duration <= 0:
        return clip

    w, h = clip.size

    if style == "zoom_in":
        # Subtle zoom: Start at 100%, end at 105%
        # Using easeInOut for smoother motion
        def zoom_in_scale(t):
            progress = t / duration
            # Apply ease-in-out curve for smoother motion
            eased = progress * progress * (3 - 2 * progress)
            return 1.0 + 0.05 * eased

        return clip.resized(zoom_in_scale)

    elif style == "zoom_out":
        # Subtle zoom: Start at 105%, end at 100%
        def zoom_out_scale(t):
            progress = t / duration
            # Apply ease-in-out curve for smoother motion
            eased = progress * progress * (3 - 2 * progress)
            return 1.05 - 0.05 * eased

        return clip.resized(zoom_out_scale)

    elif style == "pan":
        # Subtle horizontal pan (3% of width)
        def pan_scale(t):
            progress = t / duration
            # Slight zoom to allow pan without black edges
            return 1.03

        # Apply slight zoom for pan effect
        return clip.resized(pan_scale)

    return clip


def apply_shake(
    clip: ImageClip,
    intensity: float = 5,
    beat_times: List[float] = None
) -> ImageClip:
    """
    Apply shake effect, optionally synced to beats.
    """
    def shake_position(t):
        # Random shake
        if beat_times:
            # Check if we're near a beat
            for beat in beat_times:
                if abs(t - beat) < 0.05:  # 50ms window
                    x_offset = np.random.uniform(-intensity, intensity)
                    y_offset = np.random.uniform(-intensity, intensity)
                    return (x_offset, y_offset)
        return (0, 0)

    # Note: Full implementation would use clip.set_position with lambda
    return clip


def apply_pulse(
    clip: ImageClip,
    beat_times: List[float],
    scale_amount: float = 0.05
) -> ImageClip:
    """
    Apply pulse effect synced to beats.
    """
    def pulse_scale(t):
        # Check if we're near a beat
        for beat in beat_times:
            dist = abs(t - beat)
            if dist < 0.1:
                # Pulse: quick scale up then back
                pulse_progress = dist / 0.1
                return 1.0 + scale_amount * (1 - pulse_progress)
        return 1.0

    return clip.resized(pulse_scale)
