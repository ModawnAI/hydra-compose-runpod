"""Text overlay effects for video composition."""

import os
from moviepy import TextClip, CompositeVideoClip
from moviepy.video.fx import CrossFadeIn, CrossFadeOut
from typing import Tuple, Optional
import textwrap

# Get the font path relative to this file
FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
NOTO_SANS_BOLD = os.path.join(FONTS_DIR, "NotoSans-Bold.ttf")


def create_text_clip(
    text: str,
    start: float,
    duration: float,
    style: str,
    video_size: Tuple[int, int],
    font_size: Optional[int] = None
) -> TextClip:
    """
    Create a text clip with the specified style.

    Improvements:
    - Uses Noto Sans Bold 700 font for better readability
    - Larger font size (4% of height = ~77px for 1920)
    - White text with black outline for visibility
    - Position at bottom 18% for TikTok safe zone
    - Explicit text area height to prevent clipping
    - Auto line wrap for long text
    """
    width, height = video_size

    # Font size: 2.8% of height (9:16 1920 → ~54px, 16:9 1080 → ~30px)
    # Reduced to 0.7x for cleaner look
    if font_size is None:
        font_size = max(28, int(height * 0.028))

    # Auto line wrap for long text (approx 16-30 chars per line for readability)
    # Reduced chars per line for vertical videos to prevent overflow
    max_chars_per_line = 16 if width < height else 30  # Vertical vs horizontal
    wrapped_text = "\n".join(textwrap.wrap(text, width=max_chars_per_line))

    # Limit to 2 lines max for cleaner look and to prevent clipping
    lines = wrapped_text.split("\n")
    if len(lines) > 2:
        wrapped_text = "\n".join(lines[:2])
        if len(lines) > 2:
            wrapped_text = wrapped_text.rstrip() + "..."

    # Check if Noto Sans Bold font exists
    font_path = NOTO_SANS_BOLD if os.path.exists(NOTO_SANS_BOLD) else None

    # All styles now use Noto Sans Bold with white text and black outline
    style_configs = {
        "bold_pop": {
            "font": font_path,
            "color": "white",
            "stroke_color": "black",
            "stroke_width": 3,
            "method": "caption",
            "align": "center",
        },
        "fade_in": {
            "font": font_path,
            "color": "white",
            "stroke_color": "black",
            "stroke_width": 2,
            "method": "caption",
            "align": "center",
        },
        "slide_in": {
            "font": font_path,
            "color": "white",
            "stroke_color": "black",
            "stroke_width": 3,
            "method": "caption",
            "align": "center",
        },
        "minimal": {
            "font": font_path,
            "color": "white",
            "stroke_color": "black",
            "stroke_width": 2,
            "method": "caption",
            "align": "center",
        }
    }

    config = style_configs.get(style, style_configs["minimal"])

    # Text width: 85% of video width (reduced for better margins)
    text_width = int(width * 0.85)

    # Calculate text area height explicitly (prevents clipping)
    # Use generous height calculation: font_size * 1.8 per line + padding
    num_lines = len(wrapped_text.split('\n'))
    line_height = font_size * 1.8  # Generous line spacing
    text_area_height = int(num_lines * line_height + font_size)  # Extra padding

    # Create text clip with EXPLICIT height to prevent clipping
    try:
        txt_clip = TextClip(
            text=wrapped_text,
            font_size=font_size,
            font=config["font"],
            color=config["color"],
            stroke_color=config["stroke_color"],
            stroke_width=config["stroke_width"],
            method=config["method"],
            text_align=config["align"],
            size=(text_width, text_area_height)  # Explicit height!
        )
    except Exception:
        # Fallback if custom font not available
        txt_clip = TextClip(
            text=wrapped_text,
            font_size=font_size,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(text_width, text_area_height)  # Explicit height!
        )

    # Position at bottom 18% (TikTok safe zone for captions/UI elements)
    # This accounts for TikTok's bottom navigation and engagement buttons
    bottom_margin = int(height * 0.18)  # 18% from bottom edge
    y_position = height - bottom_margin - text_area_height

    # Ensure text doesn't go above 55% of screen (leave top 45% for visual content)
    min_y = int(height * 0.55)
    y_position = max(min_y, y_position)

    txt_clip = txt_clip.with_position(("center", y_position))
    txt_clip = txt_clip.with_start(start)
    txt_clip = txt_clip.with_duration(duration)

    # Apply style-specific animations using MoviePy 2.x effects
    if style == "fade_in":
        txt_clip = txt_clip.with_effects([CrossFadeIn(0.3), CrossFadeOut(0.3)])
    elif style == "bold_pop":
        txt_clip = txt_clip.with_effects([CrossFadeIn(0.15), CrossFadeOut(0.15)])
    elif style == "slide_in":
        txt_clip = txt_clip.with_effects([CrossFadeIn(0.2), CrossFadeOut(0.2)])
    else:  # minimal
        txt_clip = txt_clip.with_effects([CrossFadeIn(0.2), CrossFadeOut(0.2)])

    return txt_clip
