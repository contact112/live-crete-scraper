"""
Facebook Events Scraper
Scrapes public events from Facebook pages with cookie persistence
"""

import logging
import pickle
import time
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from bs4 import BeautifulSoup

from .selenium_manager import SeleniumManager


class FacebookScraper:
    """
    Scrapes public events from Facebook pages
    """

    def __init__(self, selenium_manager: SeleniumManager, config: Dict):
        """
        Initialize Facebook Scraper

        Args:
            selenium_manager: SeleniumManager instance
            config: Configuration dictionary
        """
        self.selenium_manager = selenium_manager
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.fb_config = config.get('facebook', {})
        self.cookies_file = Path(self.fb_config.get('cookies_file', 'cookies/facebook_cookies.pkl'))
        self.is_logged_in = False

    def _save_cookies(self):
        """
        Save current session cookies to file
        """
        try:
            driver = self.selenium_manager.get_driver()
            cookies = driver.get_cookies()

            # Create cookies directory if it doesn't exist
            self.cookies_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.cookies_file, 'wb') as f:
                pickle.dump(cookies, f)

            self.logger.info(f"Cookies saved to {self.cookies_file}")
        except Exception as e:
            self.logger.error(f"Failed to save cookies: {e}")

    def _load_cookies(self) -> bool:
        """
        Load cookies from file

        Returns:
            True if cookies loaded successfully, False otherwise
        """
        try:
            if not self.cookies_file.exists():
                self.logger.info("No cookies file found")
                return False

            driver = self.selenium_manager.get_driver()

            with open(self.cookies_file, 'rb') as f:
                cookies = pickle.load(f)

            # Navigate to Facebook first
            driver.get("https://www.facebook.com")
            time.sleep(2)

            # Add cookies
            for cookie in cookies:
                try:
                    driver.add_cookie(cookie)
                except Exception as e:
                    self.logger.debug(f"Could not add cookie: {e}")

            # Refresh page to apply cookies
            driver.refresh()
            time.sleep(3)

            # Check if logged in
            if self._is_logged_in():
                self.logger.info("Successfully loaded cookies and logged in")
                self.is_logged_in = True
                return True
            else:
                self.logger.warning("Cookies loaded but not logged in")
                return False

        except Exception as e:
            self.logger.error(f"Failed to load cookies: {e}")
            return False

    def _is_logged_in(self) -> bool:
        """
        Check if currently logged into Facebook

        Returns:
            True if logged in, False otherwise
        """
        try:
            driver = self.selenium_manager.get_driver()
            page_source = driver.page_source.lower()

            # Check for login indicators
            logged_in_indicators = [
                'logout',
                'log out',
                'account settings',
                'profile_icon'
            ]

            logged_out_indicators = [
                'create new account',
                'sign up',
                'forgotten password'
            ]

            has_logged_in = any(indicator in page_source for indicator in logged_in_indicators)
            has_logged_out = any(indicator in page_source for indicator in logged_out_indicators)

            return has_logged_in and not has_logged_out

        except Exception as e:
            self.logger.error(f"Error checking login status: {e}")
            return False

    def login(self, force_login: bool = False) -> bool:
        """
        Login to Facebook with credentials

        Args:
            force_login: Force fresh login even if cookies exist

        Returns:
            True if logged in successfully, False otherwise
        """
        try:
            # Try to load existing cookies first
            if not force_login and self.fb_config.get('save_cookies', True):
                if self._load_cookies():
                    return True

            self.logger.info("Performing fresh Facebook login...")

            driver = self.selenium_manager.get_driver()
            login_url = self.fb_config.get('login_url', 'https://www.facebook.com/login')

            # Navigate to login page
            driver.get(login_url)
            time.sleep(3)

            # Find email and password fields
            try:
                email_field = driver.find_element(By.ID, "email")
                password_field = driver.find_element(By.ID, "pass")
            except NoSuchElementException:
                # Try alternative selectors
                email_field = driver.find_element(By.NAME, "email")
                password_field = driver.find_element(By.NAME, "pass")

            # Enter credentials
            email = self.fb_config.get('email')
            password = self.fb_config.get('password')

            if not email or not password:
                self.logger.error("Facebook credentials not configured")
                return False

            email_field.clear()
            email_field.send_keys(email)
            time.sleep(1)

            password_field.clear()
            password_field.send_keys(password)
            time.sleep(1)

            # Submit login
            password_field.send_keys(Keys.RETURN)

            # Wait for login to complete
            wait_time = self.fb_config.get('facebook_login_wait', 5)
            time.sleep(wait_time)

            # Check if login successful
            if self._is_logged_in():
                self.logger.info("Facebook login successful")
                self.is_logged_in = True

                # Save cookies
                if self.fb_config.get('save_cookies', True):
                    self._save_cookies()

                return True
            else:
                self.logger.error("Facebook login failed - not logged in after submission")
                return False

        except Exception as e:
            self.logger.error(f"Failed to login to Facebook: {e}")
            return False

    def scrape_page_events(self, page_url: str) -> List[Dict]:
        """
        Scrape events from a Facebook page

        Args:
            page_url: Facebook page URL

        Returns:
            List of event dictionaries
        """
        events = []

        try:
            # Ensure logged in
            if not self.is_logged_in:
                if not self.login():
                    self.logger.error("Cannot scrape Facebook - not logged in")
                    return events

            driver = self.selenium_manager.get_driver()

            # Navigate to events tab
            events_url = self._get_events_url(page_url)
            self.logger.info(f"Scraping Facebook events from {events_url}")

            if not self.selenium_manager.navigate_to(events_url):
                self.logger.error(f"Failed to navigate to {events_url}")
                return events

            time.sleep(3)

            # Scroll to load more events
            if self.fb_config.get('infinite_scroll', True):
                max_scrolls = self.fb_config.get('max_scroll_attempts', 10)
                pause_time = self.fb_config.get('scroll_pause_time', 2)
                self.selenium_manager.infinite_scroll(max_scrolls, pause_time)

            # Parse events
            page_source = driver.page_source
            events = self._parse_events_from_html(page_source)

            self.logger.info(f"Found {len(events)} events from {page_url}")

        except Exception as e:
            self.logger.error(f"Error scraping Facebook page {page_url}: {e}")

        return events

    def _get_events_url(self, page_url: str) -> str:
        """
        Convert page URL to events URL

        Args:
            page_url: Facebook page URL

        Returns:
            Facebook events URL
        """
        # Remove trailing slash
        page_url = page_url.rstrip('/')

        # If already events URL, return as is
        if '/events' in page_url:
            return page_url

        # Add /events
        return f"{page_url}/events"

    def _parse_events_from_html(self, html: str) -> List[Dict]:
        """
        Parse events from Facebook HTML

        Args:
            html: HTML source code

        Returns:
            List of event dictionaries
        """
        events = []

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Facebook's structure changes frequently, use multiple selectors
            event_containers = self._find_event_containers(soup)

            for container in event_containers:
                try:
                    event = self._extract_event_data(container)
                    if event and event.get('title'):
                        events.append(event)
                except Exception as e:
                    self.logger.debug(f"Failed to parse event container: {e}")

        except Exception as e:
            self.logger.error(f"Error parsing Facebook HTML: {e}")

        return events

    def _find_event_containers(self, soup: BeautifulSoup) -> List:
        """
        Find event containers in BeautifulSoup object

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            List of event container elements
        """
        containers = []

        # Try various selectors (Facebook changes these frequently)
        selectors = [
            {'role': 'article'},
            {'data-testid': lambda x: x and 'event' in x.lower()},
            {'class': lambda x: x and 'event' in ' '.join(x).lower()}
        ]

        for selector in selectors:
            found = soup.find_all('div', selector)
            if found:
                containers.extend(found)

        # Remove duplicates
        containers = list(set(containers))

        return containers

    def _extract_event_data(self, container) -> Dict:
        """
        Extract event data from container element

        Args:
            container: BeautifulSoup element containing event data

        Returns:
            Event dictionary
        """
        event = {
            'title': None,
            'description': None,
            'start_date': None,
            'end_date': None,
            'venue_name': None,
            'venue_address': None,
            'image_url': None,
            'event_url': None,
            'source_type': 'Facebook'
        }

        try:
            # Extract title
            title_elem = container.find(['h2', 'h3', 'h4', 'span'], {'role': 'heading'})
            if title_elem:
                event['title'] = title_elem.get_text(strip=True)

            # Extract event URL
            link_elem = container.find('a', href=True)
            if link_elem:
                href = link_elem['href']
                if href.startswith('/'):
                    href = f"https://www.facebook.com{href}"
                event['event_url'] = href.split('?')[0]  # Remove query parameters

            # Extract image
            img_elem = container.find('img', src=True)
            if img_elem:
                event['image_url'] = img_elem['src']

            # Extract date/time (this is complex and may need adjustment)
            text = container.get_text()
            date_match = self._extract_date_from_text(text)
            if date_match:
                event['start_date'] = date_match

            # Extract location
            location_keywords = ['at ', 'in ', '·']
            for keyword in location_keywords:
                if keyword in text:
                    parts = text.split(keyword)
                    if len(parts) > 1:
                        event['venue_name'] = parts[1].split('\n')[0].strip()
                        break

            # Extract description (usually not visible in event list, would need to visit event page)
            desc_elem = container.find(['p', 'span'], {'class': lambda x: x and 'description' in ' '.join(x).lower()})
            if desc_elem:
                event['description'] = desc_elem.get_text(strip=True)

        except Exception as e:
            self.logger.debug(f"Error extracting event data: {e}")

        return event

    def _extract_date_from_text(self, text: str) -> Optional[str]:
        """
        Extract date from text using regex patterns

        Args:
            text: Text containing date

        Returns:
            ISO formatted date string or None
        """
        try:
            # Common Facebook date patterns
            patterns = [
                r'(\w{3})\s+(\d{1,2})',  # MON 15
                r'(\d{1,2})\s+(\w{3})',  # 15 MON
                r'(\w{3})\s+(\d{1,2}),\s+(\d{4})',  # MON 15, 2024
            ]

            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    # Parse date (simplified, would need proper date parsing)
                    return datetime.now().isoformat()

        except Exception as e:
            self.logger.debug(f"Failed to extract date: {e}")

        return None

    def scrape_event_details(self, event_url: str) -> Dict:
        """
        Scrape detailed information from a specific event page

        Args:
            event_url: Facebook event URL

        Returns:
            Event details dictionary
        """
        event = {}

        try:
            # Ensure logged in
            if not self.is_logged_in:
                if not self.login():
                    return event

            driver = self.selenium_manager.get_driver()

            # Navigate to event
            if not self.selenium_manager.navigate_to(event_url):
                return event

            time.sleep(3)

            # Scroll to load all content
            self.selenium_manager.scroll_page(pause_time=1, num_scrolls=2)

            # Parse event details
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            # Extract title
            title_elem = soup.find('h1')
            if title_elem:
                event['title'] = title_elem.get_text(strip=True)

            # Extract description
            desc_elem = soup.find('div', {'data-testid': lambda x: x and 'event-description' in x.lower()})
            if desc_elem:
                event['description'] = desc_elem.get_text(strip=True)

            # Extract image
            img_elem = soup.find('img', {'data-testid': lambda x: x and 'event' in x.lower()})
            if img_elem and img_elem.get('src'):
                event['image_url'] = img_elem['src']

            # Extract metadata
            event['event_url'] = event_url
            event['source_type'] = 'Facebook'

            self.logger.info(f"Scraped details for event: {event.get('title', 'Unknown')}")

        except Exception as e:
            self.logger.error(f"Error scraping event details from {event_url}: {e}")

        return event

    def logout(self):
        """
        Logout from Facebook
        """
        try:
            driver = self.selenium_manager.get_driver()
            # Navigate to logout (simplified)
            driver.get("https://www.facebook.com/logout.php")
            time.sleep(2)
            self.is_logged_in = False
            self.logger.info("Logged out from Facebook")
        except Exception as e:
            self.logger.error(f"Error logging out: {e}")
