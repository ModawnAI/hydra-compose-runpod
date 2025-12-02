"""Vibe presets for video composition."""

from .base import VibePreset
from .exciting import EXCITING_PRESET
from .emotional import EMOTIONAL_PRESET
from .pop import POP_PRESET
from .minimal import MINIMAL_PRESET


PRESETS = {
    "Exciting": EXCITING_PRESET,
    "Emotional": EMOTIONAL_PRESET,
    "Pop": POP_PRESET,
    "Minimal": MINIMAL_PRESET
}


def get_preset(vibe: str) -> VibePreset:
    """Get a preset by vibe name."""
    return PRESETS.get(vibe, MINIMAL_PRESET)


__all__ = [
    "VibePreset",
    "EXCITING_PRESET",
    "EMOTIONAL_PRESET",
    "POP_PRESET",
    "MINIMAL_PRESET",
    "PRESETS",
    "get_preset"
]
