#!/usr/bin/env python3
"""
WordPress Importer
Import scraped events to WordPress with The Events Calendar plugin
"""

import argparse
import json
import logging
import sys
import base64
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import requests
import pandas as pd
from tqdm import tqdm


class WordPressImporter:
    """
    Imports events to WordPress
    """

    def __init__(self, config_path: str = 'config.json'):
        """
        Initialize WordPress importer

        Args:
            config_path: Path to configuration file
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        self.wp_config = self.config.get('wordpress', {})

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

        # WordPress API endpoints
        self.site_url = self.wp_config.get('site_url', '').rstrip('/')
        self.api_base = f"{self.site_url}{self.wp_config.get('api_endpoint', '/wp-json/wp/v2')}"
        self.media_endpoint = f"{self.site_url}{self.wp_config.get('media_endpoint', '/wp-json/wp/v2/media')}"
        self.events_endpoint = f"{self.site_url}{self.wp_config.get('events_endpoint', '/wp-json/tribe/events/v1/events')}"

        # Authentication
        self.username = self.wp_config.get('username', '')
        self.password = self.wp_config.get('password', '')

        if not self.username or not self.password:
            self.logger.warning("WordPress credentials not configured!")

        # Create session
        self.session = requests.Session()
        self._setup_auth()

        # Stats
        self.stats = {
            'events_total': 0,
            'events_created': 0,
            'events_updated': 0,
            'events_failed': 0,
            'images_uploaded': 0,
            'categories_created': 0,
            'tags_created': 0
        }

        self.logger.info("WordPress Importer initialized")

    def _setup_auth(self):
        """
        Setup authentication for WordPress API
        """
        if self.username and self.password:
            # Basic authentication
            credentials = f"{self.username}:{self.password}"
            token = base64.b64encode(credentials.encode()).decode()
            self.session.headers.update({
                'Authorization': f'Basic {token}',
                'Content-Type': 'application/json'
            })

    def test_connection(self) -> bool:
        """
        Test WordPress API connection

        Returns:
            True if connection successful
        """
        try:
            self.logger.info(f"Testing connection to {self.site_url}")

            response = self.session.get(f"{self.site_url}/wp-json/")
            response.raise_for_status()

            self.logger.info("✓ Connection successful")
            return True

        except Exception as e:
            self.logger.error(f"✗ Connection failed: {e}")
            return False

    def load_events_from_csv(self, csv_path: str) -> List[Dict]:
        """
        Load events from CSV file

        Args:
            csv_path: Path to CSV file

        Returns:
            List of event dictionaries
        """
        self.logger.info(f"Loading events from {csv_path}")

        df = pd.read_csv(csv_path)
        events = df.to_dict('records')

        self.stats['events_total'] = len(events)
        self.logger.info(f"Loaded {len(events)} events")

        return events

    def upload_image(self, image_path: str, filename: str) -> Optional[int]:
        """
        Upload image to WordPress media library

        Args:
            image_path: Path to local image file
            filename: Filename for WordPress

        Returns:
            Media ID or None if failed
        """
        try:
            if not Path(image_path).exists():
                self.logger.warning(f"Image not found: {image_path}")
                return None

            # Read image file
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # Upload to WordPress
            headers = {
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'image/jpeg'
            }

            response = self.session.post(
                self.media_endpoint,
                headers=headers,
                data=image_data,
                auth=(self.username, self.password)
            )

            response.raise_for_status()
            media_data = response.json()

            media_id = media_data.get('id')
            self.logger.debug(f"Uploaded image: {filename} (ID: {media_id})")
            self.stats['images_uploaded'] += 1

            return media_id

        except Exception as e:
            self.logger.error(f"Failed to upload image {image_path}: {e}")
            return None

    def get_or_create_category(self, category_name: str) -> Optional[int]:
        """
        Get or create event category

        Args:
            category_name: Category name

        Returns:
            Category ID or None
        """
        if not category_name:
            return None

        try:
            # Check if category exists
            response = self.session.get(
                f"{self.api_base}/tribe_events_cat",
                params={'search': category_name}
            )

            if response.status_code == 200:
                categories = response.json()
                if categories:
                    return categories[0]['id']

            # Create category
            if self.wp_config.get('create_categories', True):
                response = self.session.post(
                    f"{self.api_base}/tribe_events_cat",
                    json={'name': category_name}
                )

                if response.status_code == 201:
                    category_id = response.json().get('id')
                    self.stats['categories_created'] += 1
                    return category_id

        except Exception as e:
            self.logger.debug(f"Category error: {e}")

        return None

    def get_or_create_tag(self, tag_name: str) -> Optional[int]:
        """
        Get or create event tag

        Args:
            tag_name: Tag name

        Returns:
            Tag ID or None
        """
        if not tag_name:
            return None

        try:
            # Check if tag exists
            response = self.session.get(
                f"{self.api_base}/post_tag",
                params={'search': tag_name}
            )

            if response.status_code == 200:
                tags = response.json()
                if tags:
                    return tags[0]['id']

            # Create tag
            if self.wp_config.get('create_tags', True):
                response = self.session.post(
                    f"{self.api_base}/post_tag",
                    json={'name': tag_name}
                )

                if response.status_code == 201:
                    tag_id = response.json().get('id')
                    self.stats['tags_created'] += 1
                    return tag_id

        except Exception as e:
            self.logger.debug(f"Tag error: {e}")

        return None

    def create_event(self, event: Dict) -> bool:
        """
        Create event in WordPress

        Args:
            event: Event dictionary

        Returns:
            True if successful
        """
        try:
            # Use French translated fields if available
            title = event.get('title_fr') or event.get('title', 'Untitled Event')
            description = event.get('description_fr') or event.get('description', '')
            excerpt = event.get('excerpt_fr') or event.get('excerpt', '')

            # Prepare event data for The Events Calendar
            event_data = {
                'title': title,
                'content': description,
                'excerpt': excerpt,
                'status': self.wp_config.get('default_status', 'publish'),
                'type': 'tribe_events',  # The Events Calendar post type
                'start_date': event.get('start_date'),
                'end_date': event.get('end_date'),
                'all_day': event.get('all_day', False),
                'timezone': event.get('timezone', 'Europe/Athens')
            }

            # Venue information
            if event.get('venue_name'):
                event_data['venue'] = {
                    'venue': event.get('venue_name_fr') or event.get('venue_name'),
                    'address': event.get('venue_address_fr') or event.get('venue_address', ''),
                    'city': event.get('venue_city_fr') or event.get('venue_city', ''),
                    'country': event.get('venue_country', 'Greece'),
                    'postal_code': event.get('venue_postal_code', ''),
                    'latitude': event.get('venue_latitude'),
                    'longitude': event.get('venue_longitude')
                }

            # Organizer information
            if event.get('organizer_name'):
                event_data['organizer'] = {
                    'organizer': event.get('organizer_name_fr') or event.get('organizer_name'),
                    'phone': event.get('organizer_phone', ''),
                    'email': event.get('organizer_email', ''),
                    'website': event.get('organizer_website', '')
                }

            # Upload featured image
            if self.wp_config.get('upload_images', True):
                image_path = event.get('image_full_path') or event.get('image_local_path')
                if image_path:
                    media_id = self.upload_image(image_path, f"{event.get('slug', 'event')}.jpg")
                    if media_id:
                        event_data['featured_media'] = media_id

            # Categories
            category_name = event.get('category_fr') or event.get('category')
            if category_name:
                category_id = self.get_or_create_category(category_name)
                if category_id:
                    event_data['categories'] = [category_id]

            # Tags
            tags = event.get('tags_fr') or event.get('tags', '')
            if tags:
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(',')]

                tag_ids = []
                for tag in tags:
                    tag_id = self.get_or_create_tag(tag)
                    if tag_id:
                        tag_ids.append(tag_id)

                if tag_ids:
                    event_data['tags'] = tag_ids

            # Additional custom fields
            event_data['meta'] = {
                '_EventCost': event.get('price', ''),
                '_EventURL': event.get('booking_url', ''),
                '_EventCapacity': event.get('capacity', '')
            }

            # Create event via REST API
            # Note: The Events Calendar might require a specific endpoint
            # This is a simplified version - adjust based on your WP setup
            response = self.session.post(
                f"{self.api_base}/tribe_events",
                json=event_data
            )

            if response.status_code in [200, 201]:
                self.stats['events_created'] += 1
                self.logger.debug(f"✓ Created: {title}")
                return True
            else:
                self.logger.warning(f"✗ Failed to create event: {response.status_code} - {response.text}")
                self.stats['events_failed'] += 1
                return False

        except Exception as e:
            self.logger.error(f"Error creating event '{event.get('title', 'Unknown')}': {e}")
            self.stats['events_failed'] += 1
            return False

    def import_events(self, events: List[Dict], batch_size: int = 10):
        """
        Import multiple events

        Args:
            events: List of events
            batch_size: Number of events per batch
        """
        self.logger.info(f"Importing {len(events)} events to WordPress...")

        for i, event in enumerate(tqdm(events, desc="Importing events")):
            self.create_event(event)

            # Pause between batches to avoid overwhelming the server
            if (i + 1) % batch_size == 0:
                self.logger.debug(f"Processed {i + 1} events, pausing...")
                import time
                time.sleep(1)

    def print_summary(self):
        """
        Print import summary
        """
        self.logger.info("="*80)
        self.logger.info("IMPORT SUMMARY")
        self.logger.info("="*80)
        self.logger.info(f"Events total: {self.stats['events_total']}")
        self.logger.info(f"Events created: {self.stats['events_created']}")
        self.logger.info(f"Events updated: {self.stats['events_updated']}")
        self.logger.info(f"Events failed: {self.stats['events_failed']}")
        self.logger.info(f"Images uploaded: {self.stats['images_uploaded']}")
        self.logger.info(f"Categories created: {self.stats['categories_created']}")
        self.logger.info(f"Tags created: {self.stats['tags_created']}")
        self.logger.info("="*80)

    def run(self, csv_path: str):
        """
        Run the import process

        Args:
            csv_path: Path to CSV file
        """
        try:
            # Test connection
            if not self.test_connection():
                self.logger.error("Cannot connect to WordPress. Check your configuration.")
                sys.exit(1)

            # Load events
            events = self.load_events_from_csv(csv_path)

            if not events:
                self.logger.warning("No events to import")
                return

            # Import events
            self.import_events(events)

            # Print summary
            self.print_summary()

            self.logger.info("\n✓ Import complete!")

        except Exception as e:
            self.logger.error(f"\n✗ Import failed: {e}", exc_info=True)
            sys.exit(1)


def main():
    """
    Main entry point
    """
    parser = argparse.ArgumentParser(
        description='Import scraped events to WordPress'
    )

    parser.add_argument(
        'csv_file',
        help='Path to CSV file with events'
    )

    parser.add_argument(
        '--config',
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='Test connection only (do not import)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of events to import (for testing)'
    )

    args = parser.parse_args()

    # Initialize importer
    importer = WordPressImporter(args.config)

    # Test connection
    if args.test:
        importer.test_connection()
        sys.exit(0)

    # Load and optionally limit events
    events = importer.load_events_from_csv(args.csv_file)

    if args.limit:
        events = events[:args.limit]
        importer.logger.info(f"Limited to {args.limit} events")

    # Import
    importer.import_events(events)
    importer.print_summary()


if __name__ == '__main__':
    main()
