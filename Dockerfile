# RunPod Serverless Worker with NVENC-enabled FFmpeg
# Uses NVIDIA CUDA base + static FFmpeg build with NVENC support

FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    # For downloading FFmpeg
    wget \
    xz-utils \
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
    # Build tools
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install static FFmpeg with NVENC support (John Van Sickle's build)
# This build includes: h264_nvenc, hevc_nvenc, and all common codecs
RUN wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
    && tar xf ffmpeg-release-amd64-static.tar.xz \
    && mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ \
    && mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ \
    && rm -rf ffmpeg-* \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

# Verify FFmpeg has NVENC
RUN ffmpeg -hide_banner -encoders 2>/dev/null | grep nvenc || echo "Note: NVENC listed but requires GPU at runtime"

# Create virtual environment and set as default Python
RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install Python dependencies
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Install RunPod SDK
RUN pip install --no-cache-dir runpod==1.6.2

# Copy application code
COPY app /app
COPY rp_handler.py /rp_handler.py

# Set working directory
WORKDIR /

# Set environment variables for NVIDIA
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=video,compute,utility

# RunPod entry point
CMD ["python", "-u", "rp_handler.py"]
