"""
Local test script for RunPod handler.
Run: python test_local.py
"""

import sys
import os

# Add paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))

# Set environment variables for S3
os.environ.setdefault("AWS_ACCESS_KEY_ID", "AKIASBF5YXJFHLVFVGQR")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "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")
os.environ.setdefault("AWS_REGION", "ap-southeast-2")
os.environ.setdefault("AWS_S3_BUCKET", "hydra-assets-hybe")

# Test input - mimics what RunPod sends
test_job = {
    "id": "test-local-001",
    "input": {
        "job_id": "compose-test-local",
        "images": [
            {"url": "https://hydra-assets-hybe.s3.ap-southeast-2.amazonaws.com/uploads/image-1.jpg", "order": 0},
            {"url": "https://hydra-assets-hybe.s3.ap-southeast-2.amazonaws.com/uploads/image-2.jpg", "order": 1},
            {"url": "https://hydra-assets-hybe.s3.ap-southeast-2.amazonaws.com/uploads/image-3.jpg", "order": 2},
        ],
        "audio": {
            "url": "https://hydra-assets-hybe.s3.ap-southeast-2.amazonaws.com/audio/test-audio.mp3",
            "start_time": 0,
            "duration": None
        },
        "script": None,
        "settings": {
            "vibe": "Pop",
            "effect_preset": "zoom_beat",
            "aspect_ratio": "9:16",
            "target_duration": 15,
            "text_style": "bold_pop",
            "color_grade": "vibrant"
        },
        "output": {
            "s3_bucket": "hydra-assets-hybe",
            "s3_key": "compose/renders/test-local/output.mp4"
        },
        "use_gpu": False  # Use CPU for local testing
    }
}

if __name__ == "__main__":
    print("=" * 60)
    print("Local Test - Hydra Compose Engine")
    print("=" * 60)

    # Import and run handler
    from rp_handler import handler

    print("\nRunning handler with test input...")
    result = handler(test_job)

    print("\n" + "=" * 60)
    print("Result:")
    print("=" * 60)
    import json
    print(json.dumps(result, indent=2))
