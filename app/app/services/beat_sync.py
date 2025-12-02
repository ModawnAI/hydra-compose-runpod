"""Beat synchronization service for video editing."""

from typing import List, Literal, Tuple
import numpy as np


# Minimum and maximum display time per image (seconds)
MIN_IMAGE_DURATION = 2.0  # Each image shown for at least 2.0 seconds (reduced for flexibility)
MAX_IMAGE_DURATION = 6.0  # Each image shown for at most 6 seconds


class BeatSyncEngine:
    """Service for synchronizing video cuts to audio beats."""

    def calculate_cuts(
        self,
        beat_times: List[float],
        num_images: int,
        target_duration: float,
        cut_style: Literal["fast", "medium", "slow"]
    ) -> List[Tuple[float, float]]:
        """
        Calculate image cut timings synced to beat points.
        Returns list of (start_time, end_time) tuples.

        BEAT-CENTRIC ALGORITHM:
        1. ALWAYS cut on beats (not between beats)
        2. Select beats closest to ideal even distribution
        3. Ensure MIN_IMAGE_DURATION between cuts
        """
        if num_images <= 0:
            return []

        # Calculate ideal duration per image
        ideal_duration = target_duration / num_images

        # If no beats, use even distribution
        if not beat_times:
            return self._even_distribution(num_images, target_duration)

        # Filter beats within target duration and add boundaries
        valid_beats = sorted(set(
            [0.0] +
            [t for t in beat_times if 0 < t < target_duration] +
            [target_duration]
        ))

        # If too few beats, use even distribution
        if len(valid_beats) < num_images + 1:
            return self._even_distribution(num_images, target_duration)

        # Select N-1 beats to create N image segments
        # Strategy: For each cut point, find the best beat that:
        #   1. Is closest to ideal position
        #   2. Respects MIN_IMAGE_DURATION from previous cut
        #   3. Leaves enough time for remaining images

        cut_points = [0.0]  # Always start at 0

        for i in range(1, num_images):
            ideal_cut = ideal_duration * i
            prev_cut = cut_points[-1]

            # Constraints
            min_cut = prev_cut + MIN_IMAGE_DURATION
            remaining_images = num_images - i
            max_cut = target_duration - (remaining_images * MIN_IMAGE_DURATION)

            # Find valid beats within constraints
            valid_candidates = [
                b for b in valid_beats
                if min_cut <= b <= max_cut and b > prev_cut
            ]

            if not valid_candidates:
                # No valid beat found - use constraint boundary
                cut_point = min(max(min_cut, ideal_cut), max_cut)
            else:
                # Style affects beat selection:
                # - fast: prefer earlier beats (more cuts, dynamic feel)
                # - slow: prefer later beats (longer shots, cinematic)
                # - medium: closest to ideal
                if cut_style == "fast":
                    # Prefer beats slightly before ideal (more dynamic)
                    candidates_before = [b for b in valid_candidates if b <= ideal_cut]
                    if candidates_before:
                        cut_point = max(candidates_before)  # Latest beat before ideal
                    else:
                        cut_point = min(valid_candidates)  # Earliest available
                elif cut_style == "slow":
                    # Prefer beats slightly after ideal (longer shots)
                    candidates_after = [b for b in valid_candidates if b >= ideal_cut]
                    if candidates_after:
                        cut_point = min(candidates_after)  # Earliest beat after ideal
                    else:
                        cut_point = max(valid_candidates)  # Latest available
                else:  # medium
                    # Closest to ideal position
                    cut_point = min(valid_candidates, key=lambda b: abs(b - ideal_cut))

            cut_points.append(cut_point)

        # Always end at target duration
        cut_points.append(target_duration)

        # Create time ranges
        cuts = []
        for i in range(num_images):
            start = cut_points[i]
            end = cut_points[i + 1]
            cuts.append((start, end))

        return cuts

    def _even_distribution(
        self,
        num_images: int,
        target_duration: float
    ) -> List[Tuple[float, float]]:
        """Fallback: perfectly even distribution without beat syncing."""
        duration_per_image = target_duration / num_images
        return [
            (i * duration_per_image, (i + 1) * duration_per_image)
            for i in range(num_images)
        ]

    def get_beat_intensity(
        self,
        energy_curve: List[Tuple[float, float]],
        time: float
    ) -> float:
        """
        Get the energy intensity at a specific time.
        Returns 0-1 value.
        """
        if not energy_curve:
            return 0.5

        # Find nearest energy points
        for i, (t, e) in enumerate(energy_curve):
            if t >= time:
                if i == 0:
                    return e
                prev_t, prev_e = energy_curve[i - 1]
                # Linear interpolation
                if t == prev_t:
                    return e
                ratio = (time - prev_t) / (t - prev_t)
                return prev_e + ratio * (e - prev_e)

        return energy_curve[-1][1] if energy_curve else 0.5

    def find_nearest_beat(
        self,
        beat_times: List[float],
        target_time: float
    ) -> float:
        """Find the nearest beat to a target time."""
        if not beat_times:
            return target_time

        return min(beat_times, key=lambda t: abs(t - target_time))

    def snap_to_beats(
        self,
        times: List[float],
        beat_times: List[float],
        tolerance: float = 0.1
    ) -> List[float]:
        """Snap a list of times to nearest beats within tolerance."""
        if not beat_times:
            return times

        snapped = []
        for t in times:
            nearest = self.find_nearest_beat(beat_times, t)
            if abs(nearest - t) <= tolerance:
                snapped.append(nearest)
            else:
                snapped.append(t)

        return snapped
