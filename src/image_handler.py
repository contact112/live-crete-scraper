"""
Image Handler
Downloads, processes, and resizes event images
"""

import logging
import requests
import hashlib
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse, urljoin
import time

from PIL import Image
import io


class ImageHandler:
    """
    Handles image downloading and processing for events
    """

    def __init__(self, config: Dict):
        """
        Initialize Image Handler

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.image_config = config.get('images', {})

        # Paths
        paths = config.get('paths', {})
        self.base_dir = Path(paths.get('images_dir', 'images/events'))
        self.full_dir = self.base_dir / 'full'
        self.medium_dir = self.base_dir / 'medium'
        self.thumb_dir = self.base_dir / 'thumbnail'

        # Ensure directories exist
        for directory in [self.full_dir, self.medium_dir, self.thumb_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        # Image sizes
        self.sizes = self.image_config.get('sizes', {
            'full': [1200, 800],
            'medium': [600, 400],
            'thumbnail': [300, 200]
        })

        # Settings
        self.timeout = self.image_config.get('download_timeout', 30)
        self.max_file_size = self.image_config.get('max_file_size_mb', 10) * 1024 * 1024
        self.quality = self.image_config.get('quality', 85)
        self.allowed_formats = self.image_config.get('allowed_formats', ['jpg', 'jpeg', 'png', 'webp'])
        self.convert_to_jpg = self.image_config.get('convert_to_jpg', True)

        # Session for downloads
        self.session = requests.Session()
        user_agents = config.get('user_agents', [])
        if user_agents:
            import random
            user_agent = random.choice(user_agents)
        else:
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive'
        })

        self.logger.info("Image handler initialized")

    def download_and_process_image(
        self,
        image_url: str,
        event_id: str,
        referer: Optional[str] = None
    ) -> Dict[str, Optional[str]]:
        """
        Download and process an image in all sizes

        Args:
            image_url: URL of the image
            event_id: Unique event identifier
            referer: Referer URL for the request

        Returns:
            Dictionary with paths to all image sizes
        """
        result = {
            'full_path': None,
            'medium_path': None,
            'thumbnail_path': None,
            'original_url': image_url,
            'success': False
        }

        if not image_url or not self.image_config.get('download_enabled', True):
            return result

        try:
            self.logger.info(f"Downloading image for event {event_id}: {image_url}")

            # Download image
            image_data = self._download_image(image_url, referer)
            if not image_data:
                return result

            # Open image
            try:
                img = Image.open(io.BytesIO(image_data))
            except Exception as e:
                self.logger.error(f"Failed to open image: {e}")
                return result

            # Convert RGBA to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background

            # Convert to RGB
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Generate filenames
            safe_id = self._sanitize_filename(event_id)

            # Save full size
            full_path = self.full_dir / f"{safe_id}_full.jpg"
            full_img = self._resize_image(img, self.sizes['full'])
            full_img.save(full_path, 'JPEG', quality=self.quality, optimize=True)
            result['full_path'] = str(full_path)
            self.logger.debug(f"Saved full image: {full_path}")

            # Save medium size
            medium_path = self.medium_dir / f"{safe_id}_medium.jpg"
            medium_img = self._resize_image(img, self.sizes['medium'])
            medium_img.save(medium_path, 'JPEG', quality=self.quality, optimize=True)
            result['medium_path'] = str(medium_path)
            self.logger.debug(f"Saved medium image: {medium_path}")

            # Save thumbnail
            thumb_path = self.thumb_dir / f"{safe_id}_thumb.jpg"
            thumb_img = self._resize_image(img, self.sizes['thumbnail'])
            thumb_img.save(thumb_path, 'JPEG', quality=self.quality, optimize=True)
            result['thumbnail_path'] = str(thumb_path)
            self.logger.debug(f"Saved thumbnail: {thumb_path}")

            result['success'] = True
            self.logger.info(f"Successfully processed image for event {event_id}")

        except Exception as e:
            self.logger.error(f"Error processing image for event {event_id}: {e}")

        return result

    def _download_image(self, url: str, referer: Optional[str] = None) -> Optional[bytes]:
        """
        Download image from URL

        Args:
            url: Image URL
            referer: Referer URL

        Returns:
            Image bytes or None
        """
        try:
            headers = {}
            if referer:
                headers['Referer'] = referer

            # Stream download to check size
            response = self.session.get(
                url,
                headers=headers,
                timeout=self.timeout,
                stream=True,
                allow_redirects=True
            )

            response.raise_for_status()

            # Check content type
            content_type = response.headers.get('Content-Type', '')
            if 'image' not in content_type.lower():
                self.logger.warning(f"URL does not return an image: {content_type}")
                return None

            # Check file size
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > self.max_file_size:
                self.logger.warning(f"Image too large: {int(content_length)} bytes")
                return None

            # Download in chunks
            chunks = []
            total_size = 0

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    total_size += len(chunk)
                    if total_size > self.max_file_size:
                        self.logger.warning("Image exceeded max size during download")
                        return None
                    chunks.append(chunk)

            image_data = b''.join(chunks)

            # Small delay to be polite
            time.sleep(0.2)

            return image_data

        except requests.RequestException as e:
            self.logger.error(f"Failed to download image from {url}: {e}")
            return None

    def _resize_image(self, img: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
        """
        Resize image while maintaining aspect ratio

        Args:
            img: PIL Image object
            target_size: Target (width, height)

        Returns:
            Resized PIL Image
        """
        # Calculate aspect ratio
        original_width, original_height = img.size
        target_width, target_height = target_size

        # Calculate scaling factor to fit within target size
        width_ratio = target_width / original_width
        height_ratio = target_height / original_height
        scale_factor = min(width_ratio, height_ratio)

        # Don't upscale if image is smaller
        if scale_factor > 1:
            scale_factor = 1

        # Calculate new dimensions
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)

        # Resize using high-quality algorithm
        resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        return resized

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to remove invalid characters

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        # Limit length
        if len(filename) > 100:
            # Use hash for very long names
            hash_suffix = hashlib.md5(filename.encode()).hexdigest()[:8]
            filename = filename[:90] + '_' + hash_suffix

        return filename

    def extract_best_image_url(self, event: Dict, page_url: str) -> Optional[str]:
        """
        Extract the best quality image URL from event data

        Args:
            event: Event dictionary
            page_url: Page URL for resolving relative URLs

        Returns:
            Best image URL or None
        """
        # Priority sources
        priority = self.image_config.get('priority_sources', [
            'og:image',
            'twitter:image',
            'schema.org image',
            'facebook event image',
            'first large image'
        ])

        # Check explicit image_url field
        if event.get('image_url'):
            return self._resolve_url(event['image_url'], page_url)

        # Check Open Graph data
        og_image = event.get('og_image')
        if og_image:
            return self._resolve_url(og_image, page_url)

        # Check schema.org data
        schema_image = event.get('schema_image')
        if schema_image:
            return self._resolve_url(schema_image, page_url)

        return None

    def _resolve_url(self, url: str, base_url: str) -> str:
        """
        Resolve relative URLs

        Args:
            url: Image URL (possibly relative)
            base_url: Base URL

        Returns:
            Absolute URL
        """
        if not url:
            return url

        # Already absolute
        if url.startswith('http://') or url.startswith('https://'):
            return url

        # Resolve relative URL
        from urllib.parse import urljoin
        return urljoin(base_url, url)

    def process_event_images(self, events: list) -> list:
        """
        Process images for multiple events

        Args:
            events: List of event dictionaries

        Returns:
            Events with image paths added
        """
        processed_events = []

        for i, event in enumerate(events):
            event_id = event.get('event_id', f'event_{i}')
            image_url = event.get('image_url')

            if image_url:
                try:
                    result = self.download_and_process_image(
                        image_url,
                        event_id,
                        referer=event.get('event_url') or event.get('source_url')
                    )

                    # Add image paths to event
                    event['image_full_path'] = result.get('full_path')
                    event['image_medium_path'] = result.get('medium_path')
                    event['image_thumbnail_path'] = result.get('thumbnail_path')
                    event['image_download_success'] = result.get('success', False)

                except Exception as e:
                    self.logger.error(f"Failed to process image for event {event_id}: {e}")

            processed_events.append(event)

        return processed_events

    def get_stats(self) -> Dict:
        """
        Get statistics about processed images

        Returns:
            Dictionary with image statistics
        """
        stats = {
            'full_images': len(list(self.full_dir.glob('*.jpg'))),
            'medium_images': len(list(self.medium_dir.glob('*.jpg'))),
            'thumbnails': len(list(self.thumb_dir.glob('*.jpg'))),
        }

        # Calculate total size
        total_size = 0
        for directory in [self.full_dir, self.medium_dir, self.thumb_dir]:
            for img_file in directory.glob('*.jpg'):
                total_size += img_file.stat().st_size

        stats['total_size_mb'] = round(total_size / (1024 * 1024), 2)

        return stats

    def cleanup_old_images(self, days: int = 30):
        """
        Remove images older than specified days

        Args:
            days: Age threshold in days
        """
        import time
        threshold = time.time() - (days * 24 * 60 * 60)

        removed_count = 0

        for directory in [self.full_dir, self.medium_dir, self.thumb_dir]:
            for img_file in directory.glob('*.jpg'):
                if img_file.stat().st_mtime < threshold:
                    try:
                        img_file.unlink()
                        removed_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to remove {img_file}: {e}")

        self.logger.info(f"Removed {removed_count} old images")
