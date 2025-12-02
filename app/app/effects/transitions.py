"""Video transition effects."""

from moviepy import (
    CompositeVideoClip,
    concatenate_videoclips,
    VideoClip
)
from moviepy.video.fx import CrossFadeIn
from typing import Callable


def apply_crossfade(
    clips: list,
    duration: float = 0.5
) -> CompositeVideoClip:
    """
    Apply crossfade transitions between clips.
    """
    if len(clips) <= 1:
        return clips[0] if clips else None

    # Adjust clip timings for overlap
    result_clips = []
    current_time = 0

    for i, clip in enumerate(clips):
        if i == 0:
            result_clips.append(clip.with_start(0))
            current_time = clip.duration - duration
        else:
            # Fade in this clip using MoviePy 2.x effects
            faded_clip = clip.with_effects([CrossFadeIn(duration)])
            result_clips.append(faded_clip.with_start(current_time))
            current_time += clip.duration - duration

    return CompositeVideoClip(result_clips)


def apply_zoom_transition(
    clips: list,
    duration: float = 0.1
) -> CompositeVideoClip:
    """
    Apply zoom transition between clips (quick zoom out/in effect).
    """
    if len(clips) <= 1:
        return clips[0] if clips else None

    # For zoom transitions, we use simple concatenation
    # The zoom effect is applied per-clip via Ken Burns
    return concatenate_videoclips(clips, method="compose")


def apply_bounce_transition(
    clips: list,
    duration: float = 0.2
) -> CompositeVideoClip:
    """
    Apply bounce transition between clips.
    """
    if len(clips) <= 1:
        return clips[0] if clips else None

    # Bounce effect: brief scale up then back to normal
    result_clips = []
    current_time = 0

    for i, clip in enumerate(clips):
        if i > 0:
            # Add a slight scale effect at the beginning
            def bounce_effect(get_frame, t, clip_duration=clip.duration):
                # Scale factor: starts at 1.1, settles to 1.0 over first 0.2s
                if t < 0.2:
                    scale = 1.1 - (0.1 * (t / 0.2))
                else:
                    scale = 1.0
                return get_frame(t)

            clip = clip.transform(lambda gf, t: bounce_effect(gf, t))

        result_clips.append(clip.with_start(current_time))
        current_time += clip.duration

    return CompositeVideoClip(result_clips)


def apply_slide_transition(
    clips: list,
    duration: float = 0.3
) -> CompositeVideoClip:
    """
    Apply slide transition between clips.
    """
    if len(clips) <= 1:
        return clips[0] if clips else None

    # Simple concatenation for now
    # Full slide implementation requires position animation
    return concatenate_videoclips(clips, method="compose")


def apply_cut_transition(
    clips: list,
    duration: float = 0.0
) -> CompositeVideoClip:
    """
    Simple cut transition (no effect).
    """
    if len(clips) <= 1:
        return clips[0] if clips else None

    return concatenate_videoclips(clips, method="compose")


TRANSITIONS = {
    "crossfade": apply_crossfade,
    "zoom_beat": apply_zoom_transition,
    "bounce": apply_bounce_transition,
    "slide": apply_slide_transition,
    "cut": apply_cut_transition,
    "minimal": apply_cut_transition  # minimal = simple cuts, no fancy transitions
}


def get_transition(
    transition_type: str
) -> Callable[[list, float], CompositeVideoClip]:
    """Get a transition function by name."""
    return TRANSITIONS.get(transition_type, apply_cut_transition)
