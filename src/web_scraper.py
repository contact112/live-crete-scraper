"""
Web Scraper for Event Websites
Intelligent scraper that uses both requests and Selenium based on site requirements
"""

import logging
import requests
import time
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime

from bs4 import BeautifulSoup
import validators

from .selenium_manager import SeleniumManager


class WebScraper:
    """
    Scrapes events from regular websites using intelligent extraction
    """

    def __init__(self, selenium_manager: Optional[SeleniumManager], config: Dict):
        """
        Initialize Web Scraper

        Args:
            selenium_manager: SeleniumManager instance (optional)
            config: Configuration dictionary
        """
        self.selenium_manager = selenium_manager
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self._setup_session()

    def _setup_session(self):
        """
        Setup requests session with headers
        """
        user_agents = self.config.get('user_agents', [])
        if user_agents:
            import random
            user_agent = random.choice(user_agents)
        else:
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

    def scrape_url(
        self,
        url: str,
        use_selenium: bool = False,
        timeout: int = 15
    ) -> List[Dict]:
        """
        Scrape events from a URL

        Args:
            url: Target URL
            use_selenium: Force use of Selenium
            timeout: Request timeout in seconds

        Returns:
            List of event dictionaries
        """
        events = []

        try:
            self.logger.info(f"Scraping {url} (selenium={use_selenium})")

            # Get HTML content
            if use_selenium:
                html = self._fetch_with_selenium(url)
            else:
                html = self._fetch_with_requests(url, timeout)

            if not html:
                self.logger.warning(f"No HTML content retrieved from {url}")
                return events

            # Parse HTML
            soup = BeautifulSoup(html, 'html.parser')

            # Try different extraction strategies
            events = self._extract_events(soup, url)

            self.logger.info(f"Found {len(events)} events from {url}")

        except Exception as e:
            self.logger.error(f"Error scraping {url}: {e}")

        return events

    def _fetch_with_requests(self, url: str, timeout: int = 15) -> Optional[str]:
        """
        Fetch HTML using requests library

        Args:
            url: Target URL
            timeout: Request timeout

        Returns:
            HTML content or None
        """
        try:
            response = self.session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()

            # Random delay
            delay_config = self.config.get('delays', {})
            import random
            delay = random.uniform(
                delay_config.get('min_delay_between_requests', 3),
                delay_config.get('max_delay_between_requests', 10)
            )
            time.sleep(delay)

            return response.text

        except requests.RequestException as e:
            self.logger.error(f"Request failed for {url}: {e}")
            return None

    def _fetch_with_selenium(self, url: str) -> Optional[str]:
        """
        Fetch HTML using Selenium

        Args:
            url: Target URL

        Returns:
            HTML content or None
        """
        try:
            if not self.selenium_manager:
                self.logger.error("Selenium manager not available")
                return None

            if self.selenium_manager.navigate_to(url):
                # Scroll to load dynamic content
                self.selenium_manager.scroll_page(pause_time=1, num_scrolls=2)

                return self.selenium_manager.get_page_source()

        except Exception as e:
            self.logger.error(f"Selenium fetch failed for {url}: {e}")

        return None

    def _extract_events(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """
        Extract events using multiple strategies

        Args:
            soup: BeautifulSoup parsed HTML
            base_url: Base URL for resolving relative links

        Returns:
            List of event dictionaries
        """
        events = []

        # Strategy 1: Schema.org structured data
        schema_events = self._extract_schema_org_events(soup, base_url)
        if schema_events:
            events.extend(schema_events)
            self.logger.debug(f"Found {len(schema_events)} events via Schema.org")

        # Strategy 2: Common event containers
        container_events = self._extract_from_containers(soup, base_url)
        if container_events:
            events.extend(container_events)
            self.logger.debug(f"Found {len(container_events)} events via containers")

        # Strategy 3: Event listing patterns
        pattern_events = self._extract_from_patterns(soup, base_url)
        if pattern_events:
            events.extend(pattern_events)
            self.logger.debug(f"Found {len(pattern_events)} events via patterns")

        return events

    def _extract_schema_org_events(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """
        Extract events from Schema.org JSON-LD or microdata

        Args:
            soup: BeautifulSoup parsed HTML
            base_url: Base URL

        Returns:
            List of events
        """
        events = []

        try:
            # Find JSON-LD scripts
            json_ld_scripts = soup.find_all('script', {'type': 'application/ld+json'})

            for script in json_ld_scripts:
                try:
                    import json
                    data = json.loads(script.string)

                    # Handle single object or array
                    if isinstance(data, dict):
                        data = [data]

                    for item in data:
                        if isinstance(item, dict):
                            event_type = item.get('@type', '')
                            if event_type in ['Event', 'SocialEvent', 'MusicEvent', 'TheaterEvent', 'SportsEvent']:
                                event = self._parse_schema_event(item, base_url)
                                if event:
                                    events.append(event)

                except Exception as e:
                    self.logger.debug(f"Failed to parse JSON-LD: {e}")

        except Exception as e:
            self.logger.error(f"Error extracting Schema.org events: {e}")

        return events

    def _parse_schema_event(self, data: Dict, base_url: str) -> Optional[Dict]:
        """
        Parse Schema.org event data

        Args:
            data: Schema.org event object
            base_url: Base URL

        Returns:
            Event dictionary
        """
        try:
            event = {
                'title': data.get('name'),
                'description': data.get('description'),
                'start_date': None,
                'end_date': None,
                'venue_name': None,
                'venue_address': None,
                'image_url': None,
                'event_url': None,
                'price': None,
                'organizer_name': None
            }

            # Start date
            start_date = data.get('startDate')
            if start_date:
                event['start_date'] = self._parse_date(start_date)

            # End date
            end_date = data.get('endDate')
            if end_date:
                event['end_date'] = self._parse_date(end_date)

            # Location
            location = data.get('location', {})
            if isinstance(location, dict):
                event['venue_name'] = location.get('name')
                address = location.get('address', {})
                if isinstance(address, dict):
                    event['venue_address'] = address.get('streetAddress')
                    event['venue_city'] = address.get('addressLocality')
                    event['venue_postal_code'] = address.get('postalCode')

            # Image
            image = data.get('image')
            if image:
                if isinstance(image, str):
                    event['image_url'] = urljoin(base_url, image)
                elif isinstance(image, list) and image:
                    event['image_url'] = urljoin(base_url, image[0])
                elif isinstance(image, dict):
                    event['image_url'] = urljoin(base_url, image.get('url', ''))

            # URL
            url = data.get('url')
            if url:
                event['event_url'] = urljoin(base_url, url)

            # Organizer
            organizer = data.get('organizer', {})
            if isinstance(organizer, dict):
                event['organizer_name'] = organizer.get('name')

            # Offers/Price
            offers = data.get('offers', {})
            if isinstance(offers, dict):
                price = offers.get('price')
                if price:
                    event['price'] = str(price)

            return event

        except Exception as e:
            self.logger.debug(f"Failed to parse schema event: {e}")
            return None

    def _extract_from_containers(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """
        Extract events from common container patterns

        Args:
            soup: BeautifulSoup parsed HTML
            base_url: Base URL

        Returns:
            List of events
        """
        events = []

        # Common event container selectors
        container_selectors = [
            {'class': lambda x: x and any(kw in ' '.join(x).lower() for kw in ['event', 'listing'])},
            {'data-type': 'event'},
            {'itemtype': lambda x: x and 'Event' in x},
        ]

        for selector in container_selectors:
            containers = soup.find_all(['div', 'article', 'li'], selector)

            for container in containers:
                try:
                    event = self._extract_event_from_container(container, base_url)
                    if event and event.get('title'):
                        events.append(event)
                except Exception as e:
                    self.logger.debug(f"Failed to extract from container: {e}")

        return events

    def _extract_event_from_container(self, container, base_url: str) -> Dict:
        """
        Extract event data from a container element

        Args:
            container: BeautifulSoup element
            base_url: Base URL

        Returns:
            Event dictionary
        """
        event = {
            'title': None,
            'description': None,
            'start_date': None,
            'image_url': None,
            'event_url': None,
            'venue_name': None
        }

        # Title
        title_elem = container.find(['h1', 'h2', 'h3', 'h4', 'a'], class_=lambda x: x and 'title' in x.lower())
        if not title_elem:
            title_elem = container.find(['h1', 'h2', 'h3', 'h4'])
        if title_elem:
            event['title'] = title_elem.get_text(strip=True)

        # URL
        link_elem = container.find('a', href=True)
        if link_elem:
            event['event_url'] = urljoin(base_url, link_elem['href'])

        # Image
        img_elem = container.find('img', src=True)
        if img_elem:
            event['image_url'] = urljoin(base_url, img_elem['src'])

        # Date
        date_elem = container.find(class_=lambda x: x and 'date' in x.lower())
        if date_elem:
            date_text = date_elem.get_text(strip=True)
            event['start_date'] = self._parse_date(date_text)

        # Description
        desc_elem = container.find(['p', 'div'], class_=lambda x: x and any(kw in x.lower() for kw in ['description', 'excerpt', 'summary']))
        if desc_elem:
            event['description'] = desc_elem.get_text(strip=True)

        # Venue
        venue_elem = container.find(class_=lambda x: x and any(kw in x.lower() for kw in ['venue', 'location']))
        if venue_elem:
            event['venue_name'] = venue_elem.get_text(strip=True)

        return event

    def _extract_from_patterns(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """
        Extract events using common pattern matching

        Args:
            soup: BeautifulSoup parsed HTML
            base_url: Base URL

        Returns:
            List of events
        """
        events = []

        # Look for common event listing patterns
        # This is a simplified version - could be expanded significantly

        # Find all links that might be events
        links = soup.find_all('a', href=True)

        for link in links:
            href = link['href']
            text = link.get_text(strip=True)

            # Skip if too short or clearly not an event
            if len(text) < 10 or not text:
                continue

            # Check if URL pattern suggests an event
            event_keywords = ['event', 'concert', 'show', 'festival', 'exhibition', 'conference']
            if any(keyword in href.lower() for keyword in event_keywords):
                event = {
                    'title': text,
                    'event_url': urljoin(base_url, href)
                }
                events.append(event)

        return events[:50]  # Limit to avoid too many false positives

    def _parse_date(self, date_str: str) -> Optional[str]:
        """
        Parse various date formats to ISO 8601

        Args:
            date_str: Date string

        Returns:
            ISO formatted date string or None
        """
        if not date_str:
            return None

        try:
            from dateutil import parser
            dt = parser.parse(date_str, fuzzy=True)
            return dt.isoformat()
        except Exception as e:
            self.logger.debug(f"Failed to parse date '{date_str}': {e}")
            return None

    def extract_open_graph_data(self, soup: BeautifulSoup, base_url: str) -> Dict:
        """
        Extract Open Graph metadata

        Args:
            soup: BeautifulSoup parsed HTML
            base_url: Base URL

        Returns:
            Dictionary of Open Graph data
        """
        og_data = {}

        try:
            og_tags = soup.find_all('meta', property=lambda x: x and x.startswith('og:'))

            for tag in og_tags:
                property_name = tag.get('property', '').replace('og:', '')
                content = tag.get('content', '')

                if property_name and content:
                    og_data[property_name] = content

                    # Resolve relative URLs
                    if property_name in ['image', 'url'] and content:
                        og_data[property_name] = urljoin(base_url, content)

        except Exception as e:
            self.logger.debug(f"Failed to extract Open Graph data: {e}")

        return og_data

    def health_check(self, url: str, timeout: int = 5) -> bool:
        """
        Check if URL is accessible

        Args:
            url: URL to check
            timeout: Timeout in seconds

        Returns:
            True if accessible, False otherwise
        """
        try:
            response = self.session.head(url, timeout=timeout, allow_redirects=True)
            return response.status_code < 400
        except Exception as e:
            self.logger.debug(f"Health check failed for {url}: {e}")
            return False
