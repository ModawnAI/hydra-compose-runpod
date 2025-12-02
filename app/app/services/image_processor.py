"""Image processing utilities."""

from PIL import Image
from typing import Tuple
import os


class ImageProcessor:
    """Service for processing images before video composition."""

    def __init__(self):
        self.supported_formats = [".jpg", ".jpeg", ".png", ".webp", ".gif"]

    def resize_for_aspect(
        self,
        image_path: str,
        aspect_ratio: str,
        output_path: str = None
    ) -> str:
        """
        Resize and crop image for target aspect ratio.
        Returns path to processed image.
        """
        ratios = {
            "9:16": (1080, 1920),
            "16:9": (1920, 1080),
            "1:1": (1080, 1080)
        }
        target_w, target_h = ratios.get(aspect_ratio, (1080, 1920))

        # Open image
        img = Image.open(image_path)

        # Convert to RGB if necessary
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img_w, img_h = img.size
        img_ratio = img_w / img_h
        target_ratio = target_w / target_h

        if img_ratio > target_ratio:
            # Image is wider - crop sides
            new_w = int(img_h * target_ratio)
            x_offset = (img_w - new_w) // 2
            img = img.crop((x_offset, 0, x_offset + new_w, img_h))
        else:
            # Image is taller - crop top/bottom
            new_h = int(img_w / target_ratio)
            y_offset = (img_h - new_h) // 2
            img = img.crop((0, y_offset, img_w, y_offset + new_h))

        # Resize to target dimensions
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        # Save
        if output_path is None:
            base, ext = os.path.splitext(image_path)
            output_path = f"{base}_processed{ext}"

        img.save(output_path, quality=95)
        return output_path

    def get_dimensions(self, image_path: str) -> Tuple[int, int]:
        """Get image dimensions."""
        with Image.open(image_path) as img:
            return img.size

    def is_valid_resolution(
        self,
        image_path: str,
        min_width: int = 720,
        min_height: int = 720
    ) -> bool:
        """Check if image meets minimum resolution requirements."""
        try:
            width, height = self.get_dimensions(image_path)
            return width >= min_width and height >= min_height
        except Exception:
            return False

    def create_thumbnail(
        self,
        image_path: str,
        output_path: str,
        size: Tuple[int, int] = (320, 320)
    ) -> str:
        """Create a thumbnail of the image."""
        with Image.open(image_path) as img:
            # Convert to RGB if necessary
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(output_path, quality=85)

        return output_path

    def is_supported_format(self, filename: str) -> bool:
        """Check if the file format is supported."""
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.supported_formats
