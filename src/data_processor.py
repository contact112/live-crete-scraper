"""
Data Processor
Validates, enriches, and deduplicates event data
"""

import logging
import re
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlparse

import validators
from dateutil import parser as date_parser
from fuzzywuzzy import fuzz
from bs4 import BeautifulSoup
import bleach
from slugify import slugify
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time


class DataProcessor:
    """
    Processes and validates event data
    """

    def __init__(self, config: Dict):
        """
        Initialize Data Processor

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.data_quality_config = config.get('data_quality', {})
        self.geocoding_config = config.get('geocoding', {})

        # Initialize geocoder
        if self.geocoding_config.get('enabled', True):
            user_agent = self.geocoding_config.get('nominatim_user_agent', 'live-crete-scraper/1.0')
            self.geocoder = Nominatim(user_agent=user_agent, timeout=10)
        else:
            self.geocoder = None

        # Cache for geocoding
        self.geocoding_cache = {}

        # Track processed events for deduplication
        self.processed_events = []

        self.logger.info("Data processor initialized")

    def process_event(self, event: Dict) -> Dict:
        """
        Process a single event (validate, clean, enrich)

        Args:
            event: Raw event dictionary

        Returns:
            Processed event dictionary
        """
        try:
            # Clean HTML from text fields
            if self.data_quality_config.get('clean_html', True):
                event = self._clean_html_fields(event)

            # Validate and normalize dates
            if self.data_quality_config.get('validate_dates', True):
                event = self._validate_dates(event)

            # Validate URLs
            if self.data_quality_config.get('validate_urls', True):
                event = self._validate_urls(event)

            # Validate email
            if self.data_quality_config.get('validate_emails', True):
                event = self._validate_email(event)

            # Geocode location
            if self.geocoding_config.get('enabled', True) and not event.get('venue_latitude'):
                event = self._geocode_location(event)

            # Generate slug
            if event.get('title') and not event.get('slug'):
                event['slug'] = self._generate_slug(event['title'])

            # Generate event ID if missing
            if not event.get('event_id'):
                event['event_id'] = self._generate_event_id(event)

            # Add metadata
            event['scraped_date'] = datetime.now().isoformat()
            event['last_updated'] = datetime.now().isoformat()

            # Set default values
            event = self._set_defaults(event)

        except Exception as e:
            self.logger.error(f"Error processing event: {e}")

        return event

    def _clean_html_fields(self, event: Dict) -> Dict:
        """
        Clean HTML from text fields

        Args:
            event: Event dictionary

        Returns:
            Event with cleaned fields
        """
        html_fields = ['title', 'subtitle', 'description', 'excerpt', 'venue_name', 'organizer_name']

        for field in html_fields:
            value = event.get(field)
            if value and isinstance(value, str):
                # Remove HTML tags
                cleaned = BeautifulSoup(value, 'html.parser').get_text()

                # Remove excessive whitespace
                cleaned = re.sub(r'\s+', ' ', cleaned).strip()

                # Remove special characters (optional)
                # cleaned = re.sub(r'[^\w\s\-.,!?;:()\[\]\'\"àáâãäåèéêëìíîïòóôõöùúûüýÿçñ]', '', cleaned)

                event[field] = cleaned

        return event

    def _validate_dates(self, event: Dict) -> Dict:
        """
        Validate and normalize date fields

        Args:
            event: Event dictionary

        Returns:
            Event with validated dates
        """
        date_fields = ['start_date', 'end_date']

        for field in date_fields:
            date_value = event.get(field)

            if date_value:
                # Parse date
                parsed_date = self._parse_date(date_value)

                if parsed_date:
                    # Convert to ISO 8601
                    event[field] = parsed_date.isoformat()
                else:
                    self.logger.warning(f"Invalid date in {field}: {date_value}")
                    event[field] = None

        # Validate date logic (end >= start)
        if event.get('start_date') and event.get('end_date'):
            try:
                start = datetime.fromisoformat(event['start_date'])
                end = datetime.fromisoformat(event['end_date'])

                if end < start:
                    self.logger.warning("End date before start date, swapping")
                    event['start_date'], event['end_date'] = event['end_date'], event['start_date']

            except Exception as e:
                self.logger.debug(f"Date comparison failed: {e}")

        # Set timezone if missing
        if event.get('start_date') and not event.get('timezone'):
            event['timezone'] = 'Europe/Athens'  # Default for Crete

        return event

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string to datetime object

        Args:
            date_str: Date string

        Returns:
            Datetime object or None
        """
        if not date_str:
            return None

        # Already ISO format
        if isinstance(date_str, datetime):
            return date_str

        try:
            # Try parsing with dateutil
            return date_parser.parse(date_str, fuzzy=True)
        except Exception as e:
            self.logger.debug(f"Failed to parse date '{date_str}': {e}")
            return None

    def _validate_urls(self, event: Dict) -> Dict:
        """
        Validate URL fields

        Args:
            event: Event dictionary

        Returns:
            Event with validated URLs
        """
        url_fields = ['event_url', 'image_url', 'booking_url', 'organizer_website', 'source_url']

        for field in url_fields:
            url = event.get(field)

            if url and isinstance(url, str):
                # Basic validation
                if not validators.url(url):
                    self.logger.warning(f"Invalid URL in {field}: {url}")
                    event[field] = None

        return event

    def _validate_email(self, event: Dict) -> Dict:
        """
        Validate email field

        Args:
            event: Event dictionary

        Returns:
            Event with validated email
        """
        email = event.get('organizer_email')

        if email and isinstance(email, str):
            if not validators.email(email):
                self.logger.warning(f"Invalid email: {email}")
                event['organizer_email'] = None

        return event

    def _geocode_location(self, event: Dict) -> Dict:
        """
        Geocode location to get coordinates

        Args:
            event: Event dictionary

        Returns:
            Event with coordinates
        """
        if not self.geocoder:
            return event

        # Build location query
        location_parts = []

        venue_name = event.get('venue_name')
        venue_address = event.get('venue_address')
        venue_city = event.get('venue_city')

        if venue_address:
            location_parts.append(venue_address)
        elif venue_name:
            location_parts.append(venue_name)

        if venue_city:
            location_parts.append(venue_city)
        else:
            # Try to extract city from region
            region = event.get('venue_region')
            if region:
                location_parts.append(region)

        # Add country
        country = event.get('venue_country') or self.geocoding_config.get('default_country', 'Greece')
        location_parts.append(country)

        location_query = ', '.join(location_parts)

        if not location_query or len(location_query) < 5:
            return event

        # Check cache
        cache_key = location_query.lower().strip()
        if cache_key in self.geocoding_cache:
            coords = self.geocoding_cache[cache_key]
            event['venue_latitude'] = coords[0]
            event['venue_longitude'] = coords[1]
            self.logger.debug(f"Using cached coordinates for: {location_query}")
            return event

        # Geocode
        try:
            self.logger.debug(f"Geocoding: {location_query}")
            location = self.geocoder.geocode(location_query)

            if location:
                event['venue_latitude'] = location.latitude
                event['venue_longitude'] = location.longitude

                # Cache result
                if self.geocoding_config.get('cache_coordinates', True):
                    self.geocoding_cache[cache_key] = (location.latitude, location.longitude)

                self.logger.info(f"Geocoded: {location_query} -> {location.latitude}, {location.longitude}")

                # Small delay to respect rate limits
                time.sleep(1)

            else:
                self.logger.warning(f"No geocoding results for: {location_query}")

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            self.logger.warning(f"Geocoding service error: {e}")
        except Exception as e:
            self.logger.error(f"Geocoding failed: {e}")

        return event

    def _generate_slug(self, title: str) -> str:
        """
        Generate URL-friendly slug from title

        Args:
            title: Event title

        Returns:
            URL slug
        """
        return slugify(title, max_length=100)

    def _generate_event_id(self, event: Dict) -> str:
        """
        Generate unique event ID

        Args:
            event: Event dictionary

        Returns:
            Unique event ID
        """
        # Create hash from key fields
        components = [
            event.get('title', ''),
            event.get('start_date', ''),
            event.get('venue_name', ''),
            event.get('source_url', '')
        ]

        hash_input = '|'.join(str(c) for c in components)
        hash_digest = hashlib.md5(hash_input.encode()).hexdigest()[:12]

        return f"evt_{hash_digest}"

    def _set_defaults(self, event: Dict) -> Dict:
        """
        Set default values for missing fields

        Args:
            event: Event dictionary

        Returns:
            Event with defaults
        """
        defaults = {
            'all_day': False,
            'timezone': 'Europe/Athens',
            'venue_country': 'Greece',
            'language': 'el',
            'featured': False,
            'status': 'publish',
            'event_type': 'event'
        }

        for key, value in defaults.items():
            if key not in event or event[key] is None:
                event[key] = value

        return event

    def deduplicate_events(self, events: List[Dict]) -> List[Dict]:
        """
        Remove duplicate events based on similarity

        Args:
            events: List of events

        Returns:
            Deduplicated list of events
        """
        if not self.data_quality_config.get('remove_duplicates', True):
            return events

        unique_events = []
        seen_hashes = set()

        threshold = self.data_quality_config.get('duplicate_threshold', 0.85) * 100

        for event in events:
            # Generate simple hash first
            simple_hash = self._generate_simple_hash(event)

            if simple_hash in seen_hashes:
                self.logger.debug(f"Exact duplicate found: {event.get('title', 'Unknown')}")
                continue

            # Check for fuzzy duplicates
            is_duplicate = False

            for unique_event in unique_events:
                similarity = self._calculate_similarity(event, unique_event)

                if similarity >= threshold:
                    self.logger.info(
                        f"Fuzzy duplicate found ({similarity:.0f}% similar): "
                        f"{event.get('title', 'Unknown')} vs {unique_event.get('title', 'Unknown')}"
                    )
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_events.append(event)
                seen_hashes.add(simple_hash)

        removed = len(events) - len(unique_events)
        self.logger.info(f"Removed {removed} duplicate events from {len(events)} total")

        return unique_events

    def _generate_simple_hash(self, event: Dict) -> str:
        """
        Generate simple hash for exact duplicate detection

        Args:
            event: Event dictionary

        Returns:
            Hash string
        """
        components = [
            event.get('title', '').lower().strip(),
            event.get('start_date', ''),
            event.get('venue_name', '').lower().strip()
        ]

        hash_input = '|'.join(components)
        return hashlib.md5(hash_input.encode()).hexdigest()

    def _calculate_similarity(self, event1: Dict, event2: Dict) -> float:
        """
        Calculate similarity between two events

        Args:
            event1: First event
            event2: Second event

        Returns:
            Similarity score (0-100)
        """
        # Compare title
        title1 = event1.get('title', '').lower().strip()
        title2 = event2.get('title', '').lower().strip()
        title_similarity = fuzz.ratio(title1, title2)

        # Compare dates
        date1 = event1.get('start_date', '')
        date2 = event2.get('start_date', '')
        date_match = 100 if date1 == date2 else 0

        # Compare venue
        venue1 = event1.get('venue_name', '').lower().strip()
        venue2 = event2.get('venue_name', '').lower().strip()
        venue_similarity = fuzz.ratio(venue1, venue2) if venue1 and venue2 else 50

        # Weighted average
        weights = {
            'title': 0.5,
            'date': 0.3,
            'venue': 0.2
        }

        similarity = (
            title_similarity * weights['title'] +
            date_match * weights['date'] +
            venue_similarity * weights['venue']
        )

        return similarity

    def validate_event(self, event: Dict) -> Tuple[bool, List[str]]:
        """
        Validate event data quality

        Args:
            event: Event dictionary

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []

        # Required fields
        required_fields = ['title', 'start_date']

        for field in required_fields:
            if not event.get(field):
                errors.append(f"Missing required field: {field}")

        # Validate title length
        title = event.get('title', '')
        min_length = self.data_quality_config.get('min_title_length', 5)
        max_length = self.data_quality_config.get('max_title_length', 200)

        if title:
            if len(title) < min_length:
                errors.append(f"Title too short (min {min_length} chars)")
            if len(title) > max_length:
                errors.append(f"Title too long (max {max_length} chars)")

        # Validate description length
        description = event.get('description', '')
        if description:
            min_desc = self.data_quality_config.get('min_description_length', 10)
            if len(description) < min_desc:
                errors.append(f"Description too short (min {min_desc} chars)")

        # Validate dates are in future (optional)
        start_date = event.get('start_date')
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                if start_dt < datetime.now():
                    # Not an error, but log it
                    self.logger.debug(f"Event date in past: {start_date}")
            except Exception:
                pass

        is_valid = len(errors) == 0

        return is_valid, errors

    def filter_events(self, events: List[Dict]) -> List[Dict]:
        """
        Filter events based on validation

        Args:
            events: List of events

        Returns:
            Filtered list of valid events
        """
        valid_events = []

        for event in events:
            is_valid, errors = self.validate_event(event)

            if is_valid:
                valid_events.append(event)
            else:
                self.logger.warning(
                    f"Event failed validation: {event.get('title', 'Unknown')} - Errors: {', '.join(errors)}"
                )

        self.logger.info(f"Filtered {len(events)} events to {len(valid_events)} valid events")

        return valid_events

    def get_processing_stats(self) -> Dict:
        """
        Get processing statistics

        Returns:
            Dictionary with stats
        """
        return {
            'geocoding_cache_size': len(self.geocoding_cache),
            'processed_events': len(self.processed_events)
        }
