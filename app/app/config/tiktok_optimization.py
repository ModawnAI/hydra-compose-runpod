"""
TikTok Video Optimization Configuration
========================================

Core principles for creating TikTok-optimized short-form videos.
This configuration is used across all video composition to ensure
maximum engagement and algorithmic favor.

Reference: TikTok Search Optimization Best Practices
- 40% of Gen Z uses TikTok as primary search engine
- Videos are "searchable assets" not just entertainment
"""

from dataclasses import dataclass
from typing import Tuple, List


# ============================================================================
# VIDEO DURATION SETTINGS
# ============================================================================

# Duration ranges by vibe/concept (in seconds)
DURATION_RANGES = {
    "Exciting": (10, 15),    # Fast-paced, high energy - shorter
    "Pop": (15, 20),         # Trendy, medium pace - balanced
    "Minimal": (15, 25),     # Clean, focused - flexible
    "Emotional": (20, 30),   # Cinematic, storytelling - longer
}

# Absolute constraints
MIN_VIDEO_DURATION = 10  # Never shorter than 10 seconds
MAX_VIDEO_DURATION = 30  # Never longer than 30 seconds (short-form sweet spot)

# Optimal durations for TikTok algorithm favor
TIKTOK_OPTIMAL_DURATION = 15  # Sweet spot for completion rate


# ============================================================================
# HOOK STRATEGY (First 3 Seconds)
# ============================================================================

@dataclass
class HookConfig:
    """Configuration for the critical first 3 seconds."""

    # Visual hook timing
    hook_duration: float = 3.0  # First 3 seconds are critical

    # Text overlay in hook
    show_keyword_text: bool = True  # Front-load keywords visually
    keyword_text_duration: float = 2.5
    keyword_text_size_multiplier: float = 1.3  # Larger than body text

    # Motion in hook (grab attention)
    hook_motion_intensity: float = 1.2  # Slightly more dynamic in hook

    # Audio hook
    audio_hook_boost: float = 1.1  # Slightly louder at start (before fade-in)


HOOK_CONFIG = HookConfig()


# ============================================================================
# TEXT OVERLAY OPTIMIZATION
# ============================================================================

@dataclass
class TextOverlayConfig:
    """Text settings optimized for TikTok viewing."""

    # Font sizing (relative to video height)
    title_size_ratio: float = 0.04      # 4% of height for titles/keywords
    body_size_ratio: float = 0.025      # 2.5% for body text
    caption_size_ratio: float = 0.02    # 2% for captions

    # Always white text with black outline for visibility
    text_color: str = "white"
    outline_color: str = "black"
    outline_width: int = 2

    # Position (safe zones for TikTok UI)
    safe_zone_top: float = 0.15     # Avoid top 15% (status bar, etc.)
    safe_zone_bottom: float = 0.20  # Avoid bottom 20% (comments, buttons)
    safe_zone_sides: float = 0.05   # 5% margin on sides

    # Text display rules
    max_chars_per_line: int = 25    # For vertical videos
    max_lines: int = 3              # Maximum 3 lines visible
    min_display_time: float = 2.0   # Each text shown at least 2 seconds

    # Animation
    fade_in_duration: float = 0.2
    fade_out_duration: float = 0.2


TEXT_CONFIG = TextOverlayConfig()


# ============================================================================
# CONTENT STRUCTURE TEMPLATES
# ============================================================================

CONTENT_STRUCTURES = {
    "list": {
        "description": "Numbered list format (5 ways to...)",
        "optimal_duration": (15, 25),
        "images_per_point": 1,
        "text_timing": "sync_with_image",
    },
    "comparison": {
        "description": "Before/after or A vs B",
        "optimal_duration": (10, 20),
        "split_screen_option": True,
        "text_timing": "comparison_labels",
    },
    "problem_solution": {
        "description": "Problem -> Solution narrative",
        "optimal_duration": (15, 25),
        "hook_type": "problem_statement",
        "resolution_emphasis": True,
    },
    "tutorial": {
        "description": "Step-by-step guide",
        "optimal_duration": (20, 30),
        "numbered_steps": True,
        "text_timing": "step_labels",
    },
    "inspiration": {
        "description": "Mood/vibe content",
        "optimal_duration": (10, 20),
        "emphasis": "visual",
        "text_timing": "minimal",
    },
}


# ============================================================================
# ENGAGEMENT OPTIMIZATION
# ============================================================================

@dataclass
class EngagementConfig:
    """Settings to maximize watch time and completion rate."""

    # Pacing
    avoid_dead_air: bool = True
    min_visual_change_interval: float = 2.5  # Something changes every 2.5s
    max_visual_change_interval: float = 5.0  # Don't exceed 5s static

    # Transitions
    transition_on_beat: bool = True
    smooth_transitions: bool = True  # Avoid jarring cuts

    # Retention hooks
    use_pattern_interrupts: bool = True  # Unexpected visual moments
    pattern_interrupt_interval: float = 7.0  # Every ~7 seconds

    # End card
    end_card_duration: float = 0.0  # No end card for short-form (let loop)
    loop_friendly: bool = True  # End should flow back to start


ENGAGEMENT_CONFIG = EngagementConfig()


# ============================================================================
# AUDIO OPTIMIZATION
# ============================================================================

@dataclass
class AudioConfig:
    """Audio settings for TikTok optimization."""

    # Fade settings
    fade_in_duration: float = 1.0   # Gentle start
    fade_out_duration: float = 2.0  # Smooth ending

    # Volume normalization
    target_loudness: float = -14.0  # LUFS (TikTok standard)

    # Beat sync
    sync_cuts_to_beats: bool = True
    beat_tolerance: float = 0.1  # Snap to beat within 100ms

    # Music recommendations
    prefer_trending_sounds: bool = True
    instrumental_preferred: bool = True  # For voiceover compatibility


AUDIO_CONFIG = AudioConfig()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_optimal_duration(vibe: str, num_images: int) -> float:
    """
    Calculate optimal video duration based on vibe and content amount.

    Args:
        vibe: The video vibe/mood preset
        num_images: Number of images in the video

    Returns:
        Optimal duration in seconds (10-30 range)
    """
    min_dur, max_dur = DURATION_RANGES.get(vibe, (15, 25))

    # Calculate based on image count (min 2.5s per image)
    content_based_duration = num_images * 2.5

    # Clamp to vibe range
    duration = max(min_dur, min(max_dur, content_based_duration))

    # Ensure within absolute limits
    return max(MIN_VIDEO_DURATION, min(MAX_VIDEO_DURATION, duration))


def get_images_for_duration(vibe: str, target_duration: float) -> Tuple[int, int]:
    """
    Calculate recommended image count for a target duration.

    Args:
        vibe: The video vibe/mood preset
        target_duration: Target video duration in seconds

    Returns:
        Tuple of (min_images, max_images)
    """
    # Based on min 2.5s and max 5s per image
    min_images = max(3, int(target_duration / 5.0))
    max_images = min(12, int(target_duration / 2.5))

    return (min_images, max_images)


def calculate_text_timing(
    total_duration: float,
    num_text_segments: int,
    vibe: str
) -> List[Tuple[float, float, float]]:
    """
    Calculate timing for text overlays.

    Returns:
        List of (start_time, end_time, duration) tuples
    """
    if num_text_segments <= 0:
        return []

    min_display = TEXT_CONFIG.min_display_time
    segment_duration = max(min_display, total_duration / num_text_segments)

    timings = []
    for i in range(num_text_segments):
        start = i * segment_duration
        end = min(start + segment_duration, total_duration)
        duration = end - start

        # Ensure minimum display time
        if duration >= min_display:
            timings.append((start, end, duration))

    return timings


# ============================================================================
# VIBE-SPECIFIC OVERRIDES
# ============================================================================

VIBE_OVERRIDES = {
    "Exciting": {
        "motion_intensity": 1.0,      # Standard (already reduced to 5%)
        "transition_speed": 0.8,      # Slightly faster transitions
        "text_animation": "bold_pop",
        "hook_emphasis": "high",
    },
    "Pop": {
        "motion_intensity": 1.0,
        "transition_speed": 1.0,
        "text_animation": "slide_in",
        "hook_emphasis": "medium",
    },
    "Minimal": {
        "motion_intensity": 0.5,      # Even more subtle
        "transition_speed": 1.2,      # Slower, cleaner
        "text_animation": "minimal",
        "hook_emphasis": "low",
    },
    "Emotional": {
        "motion_intensity": 0.8,
        "transition_speed": 1.5,      # Slow, cinematic
        "text_animation": "fade_in",
        "hook_emphasis": "medium",
    },
}
