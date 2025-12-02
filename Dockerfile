# RunPod Serverless Worker with NVENC-enabled FFmpeg
# This image has proper NVIDIA drivers and CUDA for hardware video encoding

FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies including NVENC-enabled FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    # FFmpeg with NVENC support (from Ubuntu's ffmpeg-nvidia)
    ffmpeg \
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
    # Build tools for some Python packages
    build-essential \
    && rm -rf /var/lib/apt/lists/*

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

# Set environment variables for NVENC
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=video,compute,utility

# RunPod entry point
CMD ["python", "-u", "rp_handler.py"]
