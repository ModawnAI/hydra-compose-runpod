"""Google Custom Search image fetcher."""

import httpx
from typing import List, Optional
from urllib.parse import urlparse

from ..config import get_settings
from ..models.responses import ImageCandidate, ImageSearchResult


class ImageFetcher:
    """Service for fetching images from Google Custom Search."""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.google_search_api_key
        self.cx = settings.google_search_cx
        self.base_url = "https://www.googleapis.com/customsearch/v1"

    async def search(
        self,
        query: str,
        max_results: int = 20,
        min_width: int = 720,
        min_height: int = 720,
        safe_search: str = "active"
    ) -> ImageSearchResult:
        """
        Search for images using Google Custom Search API.
        """
        if not self.api_key or not self.cx:
            # Return empty result if API not configured
            return ImageSearchResult(
                candidates=[],
                total_found=0,
                filtered=0,
                query=query
            )

        candidates = []
        filtered_count = 0

        # Google CSE returns max 10 results per request
        num_requests = (max_results + 9) // 10

        async with httpx.AsyncClient() as client:
            for i in range(num_requests):
                start_index = i * 10 + 1

                params = {
                    "key": self.api_key,
                    "cx": self.cx,
                    "q": query,
                    "searchType": "image",
                    "num": min(10, max_results - len(candidates)),
                    "start": start_index,
                    "safe": safe_search,
                    "imgSize": "large",  # Request large images
                }

                try:
                    response = await client.get(self.base_url, params=params)
                    response.raise_for_status()
                    data = response.json()

                    items = data.get("items", [])
                    for item in items:
                        image = item.get("image", {})
                        width = image.get("width", 0)
                        height = image.get("height", 0)

                        # Filter by minimum resolution
                        if width < min_width or height < min_height:
                            filtered_count += 1
                            continue

                        # Extract domain
                        source_url = item.get("link", "")
                        domain = urlparse(source_url).netloc

                        candidate = ImageCandidate(
                            source_url=source_url,
                            thumbnail_url=image.get("thumbnailLink"),
                            title=item.get("title"),
                            domain=domain,
                            width=width,
                            height=height
                        )
                        candidates.append(candidate)

                        if len(candidates) >= max_results:
                            break

                except httpx.HTTPError as e:
                    print(f"Error fetching images: {e}")
                    break

                if len(candidates) >= max_results:
                    break

        return ImageSearchResult(
            candidates=candidates,
            total_found=len(candidates) + filtered_count,
            filtered=filtered_count,
            query=query
        )

    async def download_image(
        self,
        url: str,
        output_path: str,
        timeout: float = 30.0
    ) -> Optional[str]:
        """
        Download an image from URL.
        Returns the output path on success, None on failure.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    timeout=timeout,
                    follow_redirects=True
                )
                response.raise_for_status()

                with open(output_path, "wb") as f:
                    f.write(response.content)

                return output_path

        except Exception as e:
            print(f"Error downloading image from {url}: {e}")
            return None
