#!/bin/bash
# Deploy Hydra Compose Engine to RunPod
#
# Prerequisites:
#   1. Docker installed
#   2. Docker Hub account (or RunPod registry)
#   3. RunPod account with API key
#
# Usage:
#   ./deploy.sh [docker-hub-username]
#
# Example:
#   ./deploy.sh modawnai

set -e

DOCKER_USER=${1:-"modawnai"}
IMAGE_NAME="hydra-compose-engine"
TAG="latest"
FULL_IMAGE="${DOCKER_USER}/${IMAGE_NAME}:${TAG}"

echo "=========================================="
echo "Hydra Compose Engine - RunPod Deployment"
echo "=========================================="
echo ""
echo "Docker Image: ${FULL_IMAGE}"
echo ""

# Navigate to compose-engine root
cd "$(dirname "$0")/.."

# Copy app directory to runpod build context
echo "[1/4] Copying app code to build context..."
rm -rf runpod/app
cp -r app runpod/app
echo "  ✓ App code copied"

# Build Docker image
echo ""
echo "[2/4] Building Docker image..."
cd runpod
docker build -t ${FULL_IMAGE} .
echo "  ✓ Image built: ${FULL_IMAGE}"

# Push to Docker Hub
echo ""
echo "[3/4] Pushing to Docker Hub..."
docker push ${FULL_IMAGE}
echo "  ✓ Image pushed"

# Clean up copied app directory
rm -rf app

echo ""
echo "[4/4] Deployment complete!"
echo ""
echo "=========================================="
echo "Next steps:"
echo "=========================================="
echo ""
echo "1. Go to https://www.runpod.io/console/serverless"
echo ""
echo "2. Create a new Serverless Endpoint:"
echo "   - Template: Custom"
echo "   - Docker Image: ${FULL_IMAGE}"
echo "   - GPU Type: NVIDIA T4 or RTX 3090 (for NVENC)"
echo "   - Container Disk: 20 GB"
echo "   - Volume Disk: 0 GB (we use S3)"
echo ""
echo "3. Add Environment Variables:"
echo "   - AWS_ACCESS_KEY_ID=your-key"
echo "   - AWS_SECRET_ACCESS_KEY=your-secret"
echo "   - AWS_REGION=ap-southeast-2"
echo "   - AWS_S3_BUCKET=hydra-assets-hybe"
echo ""
echo "4. Note your Endpoint ID and API Key"
echo ""
echo "5. Update Next.js to call RunPod instead of Modal"
echo ""
echo "=========================================="
