"""
Selenium Manager with Advanced Anti-Detection
Manages browser instances with stealth capabilities and fingerprint protection
"""

import random
import logging
import time
from typing import Optional, List, Dict
from pathlib import Path

import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from fake_useragent import UserAgent


class SeleniumManager:
    """
    Manages Selenium WebDriver with advanced anti-detection features
    """

    def __init__(self, config: Dict):
        """
        Initialize Selenium Manager

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.driver: Optional[webdriver.Chrome] = None
        self.user_agents: List[str] = config.get('user_agents', [])
        self.ua = UserAgent()

    def _get_random_user_agent(self) -> str:
        """
        Get a random user agent from pool or generate one

        Returns:
            Random user agent string
        """
        if self.user_agents and random.random() > 0.3:
            return random.choice(self.user_agents)

        # Fallback to fake_useragent
        try:
            return self.ua.random
        except Exception as e:
            self.logger.warning(f"Failed to generate user agent: {e}")
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def _get_chrome_options(self) -> uc.ChromeOptions:
        """
        Configure Chrome options with anti-detection settings

        Returns:
            Configured ChromeOptions object
        """
        options = uc.ChromeOptions()

        selenium_config = self.config.get('selenium', {})
        anti_detection = self.config.get('anti_detection', {})

        # Headless mode
        if selenium_config.get('headless', True):
            options.add_argument('--headless=new')

        # Window size
        window_size = selenium_config.get('window_size', [1920, 1080])
        options.add_argument(f'--window-size={window_size[0]},{window_size[1]}')

        # Anti-detection arguments
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')

        # Privacy and fingerprinting protection
        if anti_detection.get('canvas_fingerprint_defense', True):
            options.add_argument('--disable-canvas-fingerprinting')

        if anti_detection.get('webgl_fingerprint_defense', True):
            options.add_argument('--disable-webgl')
            options.add_argument('--disable-webgl2')

        # User agent
        if anti_detection.get('random_user_agent', True):
            user_agent = self._get_random_user_agent()
            options.add_argument(f'--user-agent={user_agent}')
            self.logger.debug(f"Using User-Agent: {user_agent}")

        # Disable images (optional, for performance)
        if selenium_config.get('disable_images', False):
            prefs = {
                'profile.managed_default_content_settings.images': 2,
                'profile.default_content_setting_values.images': 2
            }
            options.add_experimental_option('prefs', prefs)

        # Additional preferences
        options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
        options.add_experimental_option('useAutomationExtension', False)

        # Language
        options.add_argument('--lang=en-US,en;q=0.9')

        # Random viewport
        if anti_detection.get('random_viewport', True):
            viewport_width = random.randint(1366, 1920)
            viewport_height = random.randint(768, 1080)
            options.add_argument(f'--window-size={viewport_width},{viewport_height}')

        return options

    def _apply_stealth_scripts(self):
        """
        Apply JavaScript to make the browser less detectable
        """
        anti_detection = self.config.get('anti_detection', {})

        if not anti_detection.get('stealth_mode', True):
            return

        # Remove webdriver flag
        if anti_detection.get('disable_webdriver_flag', True):
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

        # Override permissions
        self.driver.execute_script("""
            Object.defineProperty(navigator, 'permissions', {
                get: () => ({
                    query: () => Promise.resolve({ state: 'granted' })
                })
            });
        """)

        # Override plugins
        self.driver.execute_script("""
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
        """)

        # Override languages
        self.driver.execute_script("""
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en', 'fr']
            });
        """)

        # Chrome-specific overrides
        self.driver.execute_script("""
            if (window.chrome) {
                Object.defineProperty(window, 'chrome', {
                    get: () => ({
                        runtime: {}
                    })
                });
            }
        """)

        # Canvas fingerprint protection
        if anti_detection.get('canvas_fingerprint_defense', True):
            self.driver.execute_script("""
                const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
                HTMLCanvasElement.prototype.toDataURL = function(type) {
                    if (type === 'image/png' && this.width === 16 && this.height === 16) {
                        return originalToDataURL.apply(this, arguments);
                    }
                    const context = this.getContext('2d');
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i] = imageData.data[i] ^ 1;
                    }
                    context.putImageData(imageData, 0, 0);
                    return originalToDataURL.apply(this, arguments);
                };
            """)

        self.logger.debug("Stealth scripts applied successfully")

    def create_driver(self) -> webdriver.Chrome:
        """
        Create and configure a new WebDriver instance

        Returns:
            Configured WebDriver instance
        """
        try:
            self.logger.info("Creating new Chrome WebDriver with anti-detection...")

            options = self._get_chrome_options()

            # Use undetected-chromedriver
            self.driver = uc.Chrome(
                options=options,
                version_main=None,  # Auto-detect Chrome version
                use_subprocess=True
            )

            # Set timeouts
            selenium_config = self.config.get('selenium', {})
            page_load_timeout = selenium_config.get('page_load_timeout', 15)
            implicit_wait = selenium_config.get('implicit_wait', 10)

            self.driver.set_page_load_timeout(page_load_timeout)
            self.driver.implicitly_wait(implicit_wait)

            # Apply stealth scripts
            self._apply_stealth_scripts()

            self.logger.info("WebDriver created successfully")
            return self.driver

        except Exception as e:
            self.logger.error(f"Failed to create WebDriver: {e}")
            raise

    def get_driver(self) -> webdriver.Chrome:
        """
        Get existing driver or create new one

        Returns:
            WebDriver instance
        """
        if self.driver is None:
            return self.create_driver()
        return self.driver

    def navigate_to(self, url: str, retries: int = 3) -> bool:
        """
        Navigate to URL with retry logic

        Args:
            url: Target URL
            retries: Number of retry attempts

        Returns:
            True if successful, False otherwise
        """
        driver = self.get_driver()

        for attempt in range(retries):
            try:
                self.logger.info(f"Navigating to {url} (attempt {attempt + 1}/{retries})")
                driver.get(url)

                # Random delay to appear human-like
                delay_config = self.config.get('delays', {})
                delay = random.uniform(
                    delay_config.get('min_delay_between_pages', 2),
                    delay_config.get('max_delay_between_pages', 5)
                )
                time.sleep(delay)

                return True

            except TimeoutException:
                self.logger.warning(f"Timeout loading {url}, attempt {attempt + 1}/{retries}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

            except WebDriverException as e:
                self.logger.error(f"WebDriver error: {e}")
                if attempt < retries - 1:
                    self.recreate_driver()
                    time.sleep(2 ** attempt)

        return False

    def wait_for_element(
        self,
        by: By,
        value: str,
        timeout: int = 10
    ) -> Optional[object]:
        """
        Wait for element to be present

        Args:
            by: Locator strategy
            value: Locator value
            timeout: Maximum wait time in seconds

        Returns:
            WebElement if found, None otherwise
        """
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            self.logger.warning(f"Element not found: {by}={value}")
            return None

    def scroll_page(self, pause_time: float = 1.0, num_scrolls: int = 3):
        """
        Scroll page to load dynamic content

        Args:
            pause_time: Time to wait between scrolls
            num_scrolls: Number of scroll iterations
        """
        for i in range(num_scrolls):
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause_time)

            # Scroll to random position
            scroll_position = random.randint(100, 500)
            self.driver.execute_script(f"window.scrollBy(0, -{scroll_position});")
            time.sleep(pause_time * 0.5)

    def infinite_scroll(
        self,
        max_scrolls: int = 10,
        pause_time: float = 2.0
    ) -> int:
        """
        Perform infinite scroll until no more content loads

        Args:
            max_scrolls: Maximum number of scrolls
            pause_time: Time to wait between scrolls

        Returns:
            Number of scrolls performed
        """
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scrolls = 0

        for i in range(max_scrolls):
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause_time)

            # Calculate new height
            new_height = self.driver.execute_script("return document.body.scrollHeight")

            if new_height == last_height:
                self.logger.info(f"Reached end of scrollable content after {scrolls} scrolls")
                break

            last_height = new_height
            scrolls += 1

            # Random small scroll up to simulate human behavior
            if random.random() > 0.7:
                scroll_up = random.randint(100, 300)
                self.driver.execute_script(f"window.scrollBy(0, -{scroll_up});")
                time.sleep(0.5)

        return scrolls

    def random_delay(self, min_delay: Optional[float] = None, max_delay: Optional[float] = None):
        """
        Random delay to simulate human behavior

        Args:
            min_delay: Minimum delay in seconds
            max_delay: Maximum delay in seconds
        """
        delay_config = self.config.get('delays', {})

        if min_delay is None:
            min_delay = delay_config.get('min_delay_between_requests', 3)
        if max_delay is None:
            max_delay = delay_config.get('max_delay_between_requests', 10)

        delay = random.uniform(min_delay, max_delay)
        self.logger.debug(f"Sleeping for {delay:.2f} seconds")
        time.sleep(delay)

    def take_screenshot(self, filepath: str) -> bool:
        """
        Take screenshot of current page

        Args:
            filepath: Path to save screenshot

        Returns:
            True if successful, False otherwise
        """
        try:
            self.driver.save_screenshot(filepath)
            self.logger.info(f"Screenshot saved to {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to take screenshot: {e}")
            return False

    def get_page_source(self) -> str:
        """
        Get current page source HTML

        Returns:
            Page source HTML
        """
        return self.driver.page_source

    def recreate_driver(self):
        """
        Close and recreate driver instance
        """
        self.close()
        time.sleep(2)
        self.create_driver()

    def close(self):
        """
        Close the browser and clean up
        """
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("WebDriver closed successfully")
            except Exception as e:
                self.logger.error(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None

    def __enter__(self):
        """Context manager entry"""
        self.create_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
