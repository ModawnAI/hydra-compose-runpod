# RunPod Serverless Worker with NVENC-enabled FFmpeg
# Compiled following NVIDIA Video Codec SDK official instructions

FROM nvidia/cuda:12.1.1-devel-ubuntu22.04 AS ffmpeg-builder

ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    yasm \
    cmake \
    libtool \
    libc6 \
    libc6-dev \
    unzip \
    wget \
    git \
    libnuma1 \
    libnuma-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Clone and install nv-codec-headers
RUN git clone https://git.videolan.org/git/ffmpeg/nv-codec-headers.git \
    && cd nv-codec-headers \
    && make install

# Clone FFmpeg
RUN git clone --depth 1 --branch n6.1 https://git.ffmpeg.org/ffmpeg.git ffmpeg

# Configure and build FFmpeg with NVENC support
WORKDIR /ffmpeg
RUN ./configure \
    --enable-nonfree \
    --enable-cuda-nvcc \
    --enable-libnpp \
    --enable-nvenc \
    --enable-cuvid \
    --extra-cflags="-I/usr/local/cuda/include" \
    --extra-ldflags="-L/usr/local/cuda/lib64" \
    --prefix=/usr/local \
    && make -j$(nproc) \
    && make install

# ============================================================
# Final runtime image
# ============================================================
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Copy FFmpeg from builder
COPY --from=ffmpeg-builder /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg-builder /usr/local/bin/ffprobe /usr/local/bin/ffprobe
COPY --from=ffmpeg-builder /usr/local/lib/*.so* /usr/local/lib/

# Update library cache
RUN ldconfig

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsndfile1 \
    libmpg123-0 \
    libnuma1 \
    fonts-noto-cjk \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Verify FFmpeg has NVENC
RUN ffmpeg -hide_banner -encoders 2>/dev/null | grep -E "h264_nvenc|hevc_nvenc" \
    && echo "✓ NVENC support confirmed!"

# Create virtual environment
RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
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
ENV LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH

CMD ["python", "-u", "rp_handler.py"]
