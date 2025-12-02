# RunPod Serverless Worker with NVENC-enabled FFmpeg
# Uses jrottenberg/ffmpeg which has NVENC compiled in

# Stage 1: Get FFmpeg with NVENC from jrottenberg
FROM jrottenberg/ffmpeg:6.1-nvidia AS ffmpeg

# Stage 2: Build our app
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Copy FFmpeg binaries from jrottenberg image (has NVENC!)
COPY --from=ffmpeg /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg /usr/local/bin/ffprobe /usr/local/bin/ffprobe

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    # OpenCV dependencies
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    # Audio processing
    libsndfile1 \
    libmpg123-0 \
    # Fonts for text overlays
    fonts-noto-cjk \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Verify FFmpeg has NVENC
RUN ffmpeg -hide_banner -encoders 2>/dev/null | grep -E "h264_nvenc|hevc_nvenc" && echo "NVENC support confirmed!"

# Create virtual environment
RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install dependencies
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
RUN pip install --no-cache-dir runpod==1.6.2

# Copy application code
COPY app /app
COPY rp_handler.py /rp_handler.py

WORKDIR /

# NVIDIA runtime settings
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=video,compute,utility

CMD ["python", "-u", "rp_handler.py"]
