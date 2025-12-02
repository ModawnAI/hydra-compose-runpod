"""Video color grading and filter effects."""

from moviepy import VideoClip
import numpy as np


def apply_color_grade(
    video: VideoClip,
    grade: str
) -> VideoClip:
    """
    Apply color grading to a video clip.
    """
    if grade == "vibrant":
        return _apply_vibrant(video)
    elif grade == "cinematic":
        return _apply_cinematic(video)
    elif grade == "bright":
        return _apply_bright(video)
    elif grade == "moody":
        return _apply_moody(video)
    elif grade == "bw":
        return _apply_bw(video)
    else:  # natural
        return video


def _apply_vibrant(video: VideoClip) -> VideoClip:
    """Increase saturation and contrast."""
    def process_frame(frame):
        # Increase saturation by boosting color channels
        frame = frame.astype(np.float32)
        # Simple saturation boost
        gray = np.mean(frame, axis=2, keepdims=True)
        frame = gray + 1.3 * (frame - gray)
        frame = np.clip(frame, 0, 255).astype(np.uint8)
        return frame

    return video.image_transform(process_frame)


def _apply_cinematic(video: VideoClip) -> VideoClip:
    """Apply cinematic color grading (orange/teal look)."""
    def process_frame(frame):
        frame = frame.astype(np.float32)
        # Lift shadows (blue tint)
        frame[:, :, 0] = np.clip(frame[:, :, 0] * 0.95, 0, 255)  # Red
        frame[:, :, 2] = np.clip(frame[:, :, 2] * 1.05, 0, 255)  # Blue

        # Slight desaturation
        gray = np.mean(frame, axis=2, keepdims=True)
        frame = gray + 0.9 * (frame - gray)

        # Add slight contrast
        frame = (frame - 128) * 1.1 + 128
        frame = np.clip(frame, 0, 255).astype(np.uint8)
        return frame

    return video.image_transform(process_frame)


def _apply_bright(video: VideoClip) -> VideoClip:
    """Brighten the video."""
    def process_frame(frame):
        frame = frame.astype(np.float32)
        # Increase brightness
        frame = frame * 1.1 + 10
        frame = np.clip(frame, 0, 255).astype(np.uint8)
        return frame

    return video.image_transform(process_frame)


def _apply_moody(video: VideoClip) -> VideoClip:
    """Apply moody/dark color grading (low saturation, darker, blue shadows)."""
    def process_frame(frame):
        frame = frame.astype(np.float32)
        # Darken overall
        frame = frame * 0.85

        # Add blue tint to shadows
        frame[:, :, 2] = np.clip(frame[:, :, 2] * 1.1, 0, 255)  # Blue boost

        # Desaturate
        gray = np.mean(frame, axis=2, keepdims=True)
        frame = gray + 0.7 * (frame - gray)

        # Increase contrast slightly
        frame = (frame - 128) * 1.15 + 128
        frame = np.clip(frame, 0, 255).astype(np.uint8)
        return frame

    return video.image_transform(process_frame)


def _apply_bw(video: VideoClip) -> VideoClip:
    """Convert to black and white."""
    def process_frame(frame):
        gray = np.mean(frame, axis=2, keepdims=True)
        frame = np.repeat(gray, 3, axis=2)
        return frame.astype(np.uint8)

    return video.image_transform(process_frame)


def apply_vignette(video: VideoClip, strength: float = 0.3) -> VideoClip:
    """Apply vignette effect."""
    def process_frame(frame):
        h, w = frame.shape[:2]
        # Create vignette mask
        x = np.linspace(-1, 1, w)
        y = np.linspace(-1, 1, h)
        X, Y = np.meshgrid(x, y)
        mask = 1 - strength * (X**2 + Y**2)
        mask = np.clip(mask, 0, 1)
        mask = np.stack([mask] * 3, axis=2)

        frame = frame.astype(np.float32) * mask
        return np.clip(frame, 0, 255).astype(np.uint8)

    return video.image_transform(process_frame)


def apply_film_grain(video: VideoClip, intensity: float = 0.05) -> VideoClip:
    """Apply film grain effect."""
    def process_frame(frame):
        h, w = frame.shape[:2]
        noise = np.random.normal(0, intensity * 255, (h, w, 3))
        frame = frame.astype(np.float32) + noise
        return np.clip(frame, 0, 255).astype(np.uint8)

    return video.image_transform(process_frame)
