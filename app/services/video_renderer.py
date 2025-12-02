"""Main video rendering service using MoviePy."""

import os
import asyncio
import logging
from typing import Callable, Optional, List
from moviepy import (
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips
)
from moviepy.audio.fx import AudioFadeIn, AudioFadeOut

from .audio_analyzer import AudioAnalyzer
from .beat_sync import BeatSyncEngine, MIN_IMAGE_DURATION
from .image_processor import ImageProcessor
from ..effects import transitions, filters, text_overlay, motion
from ..presets import get_preset
from ..utils.s3_client import S3Client
from ..utils.temp_files import TempFileManager
from ..models.render_job import (
    RenderRequest,
    ImageData,
    AudioData,
    ScriptData,
    RenderSettings
)


logger = logging.getLogger(__name__)

# Audio fade durations (seconds)
AUDIO_FADE_IN = 1.0   # Gentle fade in at start
AUDIO_FADE_OUT = 2.0  # Smooth fade out at end

# TikTok Hook Strategy Constants
HOOK_DURATION = 2.0  # First 2 seconds for hook (calm before beat drop)
HOOK_CALM_FACTOR = 0.7  # Reduce audio volume in hook section


class VideoRenderer:
    """Main service for rendering composed videos."""

    def __init__(self):
        self.s3 = S3Client()
        self.audio_analyzer = AudioAnalyzer()
        self.beat_sync = BeatSyncEngine()
        self.image_processor = ImageProcessor()
        self.temp = TempFileManager()

    async def render(
        self,
        request: RenderRequest,
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        Main rendering pipeline.
        Returns S3 URL of rendered video.
        """
        job_id = request.job_id
        job_dir = self.temp.get_job_dir(job_id)

        try:
            # Log render request details
            logger.info(f"[{job_id}] Starting render with {len(request.images)} images")
            logger.info(f"[{job_id}] Vibe: {request.settings.vibe.value}, Target duration: {request.settings.target_duration}")
            if request.script and request.script.lines:
                logger.info(f"[{job_id}] Script lines: {len(request.script.lines)}")
                for i, line in enumerate(request.script.lines):
                    logger.info(f"[{job_id}]   Line {i}: '{line.text}' at {line.timing}s for {line.duration}s")
            else:
                logger.info(f"[{job_id}] No script lines provided")

            # Step 1: Download images
            await self._update_progress(progress_callback, job_id, 0, "Downloading images")
            image_paths = await self._download_images(request.images, job_dir)

            # Step 2: Download audio
            await self._update_progress(progress_callback, job_id, 10, "Downloading audio")
            audio_path = await self._download_audio(request.audio, job_dir)

            # Step 3: Analyze audio
            await self._update_progress(progress_callback, job_id, 15, "Analyzing audio beats")
            audio_analysis = self.audio_analyzer.analyze(audio_path)
            beat_times = audio_analysis.beat_times

            # Step 4: Get preset and calculate cut timings
            await self._update_progress(progress_callback, job_id, 20, "Calculating cut timings")
            preset = get_preset(request.settings.vibe.value)

            # Auto-calculate target duration based on TikTok optimization
            # Each preset has duration_range (min, max) optimized for TikTok (10-30 seconds)
            num_images = len(image_paths)
            audio_duration = audio_analysis.duration

            # Get preset's recommended duration range
            min_duration, max_duration = preset.duration_range

            # Calculate minimum duration required for all images
            min_duration_for_images = num_images * MIN_IMAGE_DURATION

            # PRIORITY: Show ALL images within TikTok-optimal duration
            # CRITICAL: Respect preset's max_duration (TikTok: 15-30 seconds)

            if request.settings.target_duration and request.settings.target_duration > 0:
                # User specified duration - use it but ensure all images fit
                target_duration = max(min_duration_for_images, request.settings.target_duration)
                target_duration = min(target_duration, audio_duration, max_duration)
                logger.info(f"[{job_id}] Using user-specified duration: {target_duration}s")
            else:
                # Auto-calculate: TikTok-optimal duration
                # Target: All images shown with ideal per-image duration (3s each)
                IDEAL_PER_IMAGE = 3.0  # 3 seconds per image is optimal for TikTok
                ideal_duration = num_images * IDEAL_PER_IMAGE

                # Clamp to preset's range (CRITICAL: respect max_duration!)
                target_duration = max(min_duration, min_duration_for_images, ideal_duration)
                target_duration = min(target_duration, max_duration, audio_duration)

                # Log why we chose this duration
                if target_duration == max_duration:
                    logger.info(f"[{job_id}] Capped to preset max_duration: {max_duration}s")
                elif target_duration == audio_duration:
                    logger.info(f"[{job_id}] Limited by audio duration: {audio_duration}s")

            # Final check: ensure all images can fit
            if target_duration < min_duration_for_images:
                target_duration = min(min_duration_for_images, audio_duration)
                logger.warning(f"[{job_id}] Forcing min duration for {num_images} images: {target_duration}s")

            logger.info(f"[{job_id}] Min duration for {num_images} images: {min_duration_for_images}s")
            logger.info(f"[{job_id}] Ideal per image: {target_duration/num_images:.1f}s")

            logger.info(f"[{job_id}] Calculated target duration: {target_duration}s (range: {min_duration}-{max_duration}s)")
            logger.info(f"[{job_id}] Audio duration: {audio_duration}s, Images: {num_images}")

            cut_times = self.beat_sync.calculate_cuts(
                beat_times=beat_times,
                num_images=num_images,
                target_duration=target_duration,
                cut_style=preset.cut_style
            )

            # Log cut times for each image (debugging)
            logger.info(f"[{job_id}] Cut times for {len(cut_times)} images:")
            for i, (start, end) in enumerate(cut_times):
                duration = end - start
                logger.info(f"[{job_id}]   Image {i+1}: {start:.1f}s - {end:.1f}s ({duration:.1f}s)")

            # Step 5: Process images IN PARALLEL using ThreadPool
            await self._update_progress(progress_callback, job_id, 25, "Processing images")
            from concurrent.futures import ThreadPoolExecutor

            def process_single_image(args):
                idx, img_path = args
                return self.image_processor.resize_for_aspect(
                    img_path,
                    request.settings.aspect_ratio.value,
                    self.temp.get_path(job_id, f"processed_{idx}.jpg")
                )

            # Process all images in parallel with ThreadPoolExecutor
            logger.info(f"[{job_id}] Processing {len(image_paths)} images in parallel...")
            with ThreadPoolExecutor(max_workers=min(8, len(image_paths))) as executor:
                processed_paths = list(executor.map(
                    process_single_image,
                    enumerate(image_paths)
                ))
            logger.info(f"[{job_id}] Processed {len(processed_paths)} images")

            # Step 6: Create image clips with effects
            await self._update_progress(progress_callback, job_id, 30, "Creating image clips")
            clips = []
            for i, (img_path, (start, end)) in enumerate(zip(processed_paths, cut_times)):
                clip = self._create_image_clip(
                    img_path=img_path,
                    start=start,
                    end=end,
                    preset=preset,
                    aspect_ratio=request.settings.aspect_ratio.value,
                    beat_times=beat_times
                )
                clips.append(clip)

                progress = 30 + int(25 * (i + 1) / len(processed_paths))
                await self._update_progress(
                    progress_callback, job_id, progress,
                    f"Processing image {i + 1}/{len(processed_paths)}"
                )

            # Step 7: Apply transitions
            # Use effect_preset from request if specified, otherwise use preset's default
            await self._update_progress(progress_callback, job_id, 55, "Applying transitions")
            effect_preset = request.settings.effect_preset.value if request.settings.effect_preset else preset.transition_type
            logger.info(f"[{job_id}] Using transition/effect: {effect_preset}")
            transition_func = transitions.get_transition(effect_preset)
            video = transition_func(clips, duration=preset.transition_duration)

            # Step 8: Add text overlays
            await self._update_progress(progress_callback, job_id, 65, "Adding text overlays")
            video_duration = video.duration
            logger.info(f"[{job_id}] Video duration before text: {video_duration}s")

            if request.script and request.script.lines:
                # Recalculate script timings to fit within video duration
                adjusted_script = self._adjust_script_timings(
                    request.script,
                    video_duration,
                    job_id
                )
                logger.info(f"[{job_id}] Adding {len(adjusted_script.lines)} text overlays")
                video = self._add_text_overlays(
                    video,
                    adjusted_script,
                    request.settings.text_style.value,
                    request.settings.aspect_ratio.value
                )
            else:
                logger.info(f"[{job_id}] Skipping text overlays (no script data)")

            # Step 9: Add audio with fade in/out
            await self._update_progress(progress_callback, job_id, 75, "Adding audio track")
            audio_clip = AudioFileClip(audio_path)

            # Track ALL audio clips for proper cleanup (critical for Windows file locks)
            audio_clips_to_close = [audio_clip]

            # Update video_duration after potential text overlay changes
            video_duration = video.duration
            logger.info(f"[{job_id}] Final video duration: {video_duration}s")

            # Trim audio to match video duration
            if request.audio.start_time or request.audio.duration:
                start = request.audio.start_time or 0
                duration = request.audio.duration or video_duration
                trimmed = audio_clip.subclipped(start, start + min(duration, audio_clip.duration - start))
                audio_clips_to_close.append(trimmed)
                audio_clip = trimmed

            # Ensure audio matches video duration
            if audio_clip.duration > video_duration:
                trimmed = audio_clip.subclipped(0, video_duration)
                audio_clips_to_close.append(trimmed)
                audio_clip = trimmed

            # TikTok Hook Strategy: Calm start (70% volume) then beat drop (100% volume)
            # Split audio at hook point and apply different volumes
            if audio_clip.duration > HOOK_DURATION:
                from moviepy import concatenate_audioclips
                # Split into hook section and main section
                hook_section = audio_clip.subclipped(0, HOOK_DURATION).with_volume_scaled(HOOK_CALM_FACTOR)
                main_section = audio_clip.subclipped(HOOK_DURATION, audio_clip.duration)
                audio_clips_to_close.extend([hook_section, main_section])
                audio_clip = concatenate_audioclips([hook_section, main_section])
                audio_clips_to_close.append(audio_clip)
            logger.info(f"[{job_id}] Applied TikTok hook audio effect (calm {HOOK_DURATION}s → beat drop)")

            # Apply audio fade effects for smooth start and end
            # Fade in at start (1 second gentle rise)
            # Fade out at end (2 seconds smooth fade)
            faded_clip = audio_clip.with_effects([
                AudioFadeIn(AUDIO_FADE_IN),
                AudioFadeOut(AUDIO_FADE_OUT)
            ])
            audio_clips_to_close.append(faded_clip)
            audio_clip = faded_clip

            video = video.with_audio(audio_clip)

            # Step 10: Apply color grading
            await self._update_progress(progress_callback, job_id, 80, "Applying color grading")
            video = filters.apply_color_grade(video, request.settings.color_grade.value)

            # Step 11: Render to file
            await self._update_progress(progress_callback, job_id, 85, "Rendering final video")
            output_path = self.temp.get_path(job_id, "output.mp4")
            # CRITICAL: Use job-specific temp audio file to avoid conflicts in parallel processing
            temp_audiofile = self.temp.get_path(job_id, f"temp_audio_{job_id}.mp4")

            # Check if NVENC (GPU encoding) is available and requested
            use_nvenc = os.environ.get("USE_NVENC", "0") == "1"

            if use_nvenc:
                # NVENC: NVIDIA GPU hardware encoding
                # Settings from NVIDIA Video Codec SDK documentation:
                # https://docs.nvidia.com/video-technologies/video-codec-sdk/ffmpeg-with-nvidia-gpu/
                logger.info(f"[{job_id}] Rendering video with NVENC (GPU)")
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: video.write_videofile(
                        output_path,
                        fps=30,
                        codec="h264_nvenc",
                        audio_codec="aac",
                        threads=4,
                        ffmpeg_params=[
                            "-preset", "p4",        # Medium speed/quality balance
                            "-tune", "hq",          # High quality tuning
                            "-rc", "vbr",           # Variable bitrate mode
                            "-cq", "19",            # Constant quality (lower = better)
                            "-b:v", "8M",           # Target bitrate
                            "-maxrate", "12M",      # Max bitrate
                            "-bufsize", "16M",      # Buffer size
                            "-rc-lookahead", "20",  # Lookahead frames for better quality
                            "-bf", "3",             # B-frames
                            "-b_ref_mode", "middle",# B-frame reference mode
                            "-temporal-aq", "1",    # Temporal adaptive quantization
                            "-movflags", "+faststart"
                        ],
                        temp_audiofile=temp_audiofile,
                        logger=None
                    )
                )
            else:
                # libx264: CPU encoding (reliable fallback)
                logger.info(f"[{job_id}] Rendering video with libx264 (CPU)")
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: video.write_videofile(
                        output_path,
                        fps=30,
                        codec="libx264",
                        audio_codec="aac",
                        preset="fast",
                        threads=4,
                        ffmpeg_params=["-crf", "20", "-movflags", "+faststart"],
                        temp_audiofile=temp_audiofile,
                        logger=None
                    )
                )
            logger.info(f"[{job_id}] Video rendered successfully")

            # Close all clips to release file handles (critical for Windows)
            # Close all tracked audio clips (including intermediate clips from hook processing)
            for aclip in audio_clips_to_close:
                try:
                    aclip.close()
                except Exception:
                    pass
            try:
                video.close()
            except Exception:
                pass
            for clip in clips:
                try:
                    clip.close()
                except Exception:
                    pass

            # Force garbage collection to release file handles immediately
            import gc
            gc.collect()

            # Step 12: Upload to S3
            await self._update_progress(progress_callback, job_id, 95, "Uploading to storage")
            s3_url = await self.s3.upload_file(
                output_path,
                request.output.s3_key,
                content_type="video/mp4"
            )

            # Cleanup
            self.temp.cleanup(job_id)

            await self._update_progress(progress_callback, job_id, 100, "Completed")
            return s3_url

        except Exception as e:
            self.temp.cleanup(job_id)
            raise e

    async def _download_images(
        self,
        images: List[ImageData],
        job_dir: str
    ) -> List[str]:
        """Download all images in PARALLEL for faster processing."""
        sorted_images = sorted(images, key=lambda x: x.order)

        async def download_single(idx: int, image: ImageData) -> tuple[int, str]:
            local_path = os.path.join(job_dir, f"image_{idx}.jpg")
            await self.s3.download_file(image.url, local_path)
            return idx, local_path

        # Download ALL images in parallel using asyncio.gather
        logger.info(f"Downloading {len(sorted_images)} images in parallel...")
        tasks = [download_single(i, img) for i, img in enumerate(sorted_images)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Sort by index and extract paths, handling any errors
        paths = []
        for result in sorted(results, key=lambda x: x[0] if isinstance(x, tuple) else float('inf')):
            if isinstance(result, Exception):
                logger.error(f"Image download failed: {result}")
                raise result
            paths.append(result[1])

        logger.info(f"Downloaded {len(paths)} images successfully")
        return paths

    async def _download_audio(
        self,
        audio: AudioData,
        job_dir: str
    ) -> str:
        """Download audio to local storage."""
        local_path = os.path.join(job_dir, "audio.mp3")
        await self.s3.download_file(audio.url, local_path)
        return local_path

    def _create_image_clip(
        self,
        img_path: str,
        start: float,
        end: float,
        preset,
        aspect_ratio: str,
        beat_times: List[float]
    ) -> ImageClip:
        """Create a single image clip with motion effects."""
        duration = end - start

        # Create clip
        clip = ImageClip(img_path).with_duration(duration)

        # Apply Ken Burns effect
        clip = motion.apply_ken_burns(
            clip,
            style=preset.motion_style,
            beat_times=[t - start for t in beat_times if start <= t < end]
        )

        return clip.with_start(start)

    def _adjust_script_timings(
        self,
        script: ScriptData,
        video_duration: float,
        job_id: str
    ) -> ScriptData:
        """
        Adjust script timings to fit within the actual video duration.
        CRITICAL: Ensures NO OVERLAP between subtitles with explicit gap.
        """
        from ..models.render_job import ScriptLine

        if not script.lines:
            return script

        num_lines = len(script.lines)
        logger.info(f"[{job_id}] Adjusting {num_lines} script lines for {video_duration}s video")

        # Gap between subtitles (prevents overlap)
        SUBTITLE_GAP = 0.5  # 0.5 second gap between subtitles
        MIN_SUBTITLE_DURATION = 1.5  # Minimum display time
        MAX_SUBTITLE_DURATION = 4.0  # Maximum display time

        adjusted_lines = []

        if num_lines == 1:
            # Single line: show in middle portion of video
            line = script.lines[0]
            adjusted_lines.append(ScriptLine(
                text=line.text,
                timing=0.5,
                duration=min(video_duration - 1.0, MAX_SUBTITLE_DURATION)
            ))
        else:
            # Calculate total available time for subtitles
            total_available = video_duration - 0.5  # Leave margin at end
            total_gaps = (num_lines - 1) * SUBTITLE_GAP
            total_subtitle_time = total_available - total_gaps

            # Duration per subtitle (evenly distributed)
            duration_per_subtitle = total_subtitle_time / num_lines
            duration_per_subtitle = max(MIN_SUBTITLE_DURATION, min(MAX_SUBTITLE_DURATION, duration_per_subtitle))

            # If not enough time, reduce gap
            if duration_per_subtitle * num_lines + total_gaps > total_available:
                # Recalculate with minimum duration
                duration_per_subtitle = MIN_SUBTITLE_DURATION
                SUBTITLE_GAP = max(0.2, (total_available - duration_per_subtitle * num_lines) / max(1, num_lines - 1))

            current_time = 0.3  # Start slightly after video begins

            for i, line in enumerate(script.lines):
                # Calculate timing ensuring NO OVERLAP
                timing = current_time
                duration = duration_per_subtitle

                # Ensure we don't exceed video duration
                if timing + duration > video_duration - 0.3:
                    duration = video_duration - timing - 0.3
                    if duration < 1.0:
                        logger.warning(f"[{job_id}] Skipping subtitle {i}: not enough time")
                        continue

                adjusted_lines.append(ScriptLine(
                    text=line.text,
                    timing=timing,
                    duration=duration
                ))

                # Move to next position (end of current + gap)
                current_time = timing + duration + SUBTITLE_GAP

        # Log adjusted timings and verify no overlap
        for i, line in enumerate(adjusted_lines):
            end_time = line.timing + line.duration
            logger.info(f"[{job_id}]   Subtitle {i}: '{line.text[:20]}...' [{line.timing:.1f}s - {end_time:.1f}s]")

            # Verify no overlap with next subtitle
            if i < len(adjusted_lines) - 1:
                next_start = adjusted_lines[i + 1].timing
                if end_time > next_start:
                    logger.error(f"[{job_id}]   OVERLAP DETECTED: {end_time:.1f} > {next_start:.1f}")

        return ScriptData(lines=adjusted_lines)

    def _add_text_overlays(
        self,
        video: CompositeVideoClip,
        script: ScriptData,
        style: str,
        aspect_ratio: str
    ) -> CompositeVideoClip:
        """Add script text as overlays."""
        # Get video size
        sizes = {
            "9:16": (1080, 1920),
            "16:9": (1920, 1080),
            "1:1": (1080, 1080)
        }
        video_size = sizes.get(aspect_ratio, (1080, 1920))

        text_clips = [video]
        for line in script.lines:
            try:
                txt_clip = text_overlay.create_text_clip(
                    text=line.text,
                    start=line.timing,
                    duration=line.duration,
                    style=style,
                    video_size=video_size
                )
                text_clips.append(txt_clip)
                logger.info(f"Created text clip: '{line.text[:20]}...' at {line.timing}s")
            except Exception as e:
                logger.error(f"Failed to create text clip: {e}")
                continue

        return CompositeVideoClip(text_clips)

    async def _update_progress(
        self,
        callback: Optional[Callable],
        job_id: str,
        progress: int,
        step: str
    ):
        """Update progress via callback if provided."""
        if callback:
            await callback(job_id, progress, step)
