"""
Live Crete Events Scraper
Ultra-performant scraper for 202 Crete event sources
"""

__version__ = "1.0.0"
__author__ = "Live Crete Manager"
__description__ = "Professional web scraper for Crete events with Facebook integration, translation, and image processing"

from .selenium_manager import SeleniumManager
from .facebook_scraper import FacebookScraper
from .web_scraper import WebScraper
from .translator import Translator
from .image_handler import ImageHandler
from .data_processor import DataProcessor
from .csv_exporter import CSVExporter
from .cache_manager import CacheManager

__all__ = [
    'SeleniumManager',
    'FacebookScraper',
    'WebScraper',
    'Translator',
    'ImageHandler',
    'DataProcessor',
    'CSVExporter',
    'CacheManager',
]
