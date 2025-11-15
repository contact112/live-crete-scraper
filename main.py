#!/usr/bin/env python3
"""
Live Crete Events Scraper - Main Script
Ultra-performant scraper for 202 Crete event sources
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from datetime import datetime

import pandas as pd
from tqdm import tqdm
import colorlog

from src.selenium_manager import SeleniumManager
from src.facebook_scraper import FacebookScraper
from src.web_scraper import WebScraper
from src.translator import Translator
from src.image_handler import ImageHandler
from src.data_processor import DataProcessor
from src.csv_exporter import CSVExporter
from src.cache_manager import CacheManager


class CreteScraper:
    """
    Main scraper orchestrator
    """

    def __init__(self, config_path: str = 'config.json'):
        """
        Initialize scraper

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        # Setup logging
        self._setup_logging()

        self.logger = logging.getLogger(__name__)
        self.logger.info("="*80)
        self.logger.info("Live Crete Events Scraper v1.0")
        self.logger.info("="*80)

        # Initialize components
        self.cache_manager = CacheManager(self.config)
        self.translator = Translator(self.config)
        self.image_handler = ImageHandler(self.config)
        self.data_processor = DataProcessor(self.config)
        self.csv_exporter = CSVExporter(self.config)

        # Selenium and scrapers (initialized per thread)
        self.selenium_manager = None
        self.facebook_scraper = None
        self.web_scraper = None

        # Storage
        self.all_events = []
        self.failed_sources = []
        self.stats = {
            'sources_total': 0,
            'sources_scraped': 0,
            'sources_failed': 0,
            'events_total': 0,
            'events_valid': 0,
            'events_duplicates': 0,
            'images_downloaded': 0,
            'events_translated': 0,
            'start_time': None,
            'end_time': None
        }

    def _setup_logging(self):
        """
        Configure logging with colors and file output
        """
        log_config = self.config.get('logging', {})

        # Create logs directory
        logs_dir = Path(self.config['paths']['logs_dir'])
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Log level
        level = getattr(logging, log_config.get('level', 'INFO'))

        # Root logger
        logger = logging.getLogger()
        logger.setLevel(level)

        # Remove existing handlers
        logger.handlers = []

        # Console handler with colors
        if log_config.get('console_output', True):
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)

            # Color formatter
            color_formatter = colorlog.ColoredFormatter(
                '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S',
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                }
            )
            console_handler.setFormatter(color_formatter)
            logger.addHandler(console_handler)

        # File handler
        if log_config.get('file_output', True):
            log_filename = log_config.get('log_filename', 'scraper_{date}.log')
            log_filename = log_filename.format(date=datetime.now().strftime('%Y%m%d'))
            log_file = logs_dir / log_filename

            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(level)

            file_formatter = logging.Formatter(
                log_config.get('log_format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
                datefmt=log_config.get('date_format', '%Y-%m-%d %H:%M:%S')
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

    def load_sources(self) -> List[Dict]:
        """
        Load sources from CSV

        Returns:
            List of source dictionaries
        """
        sources_path = self.config['paths']['sources_csv']
        self.logger.info(f"Loading sources from {sources_path}")

        df = pd.read_csv(sources_path)

        # Filter active sources
        df = df[df['active'] == 'yes']

        sources = df.to_dict('records')

        self.stats['sources_total'] = len(sources)
        self.logger.info(f"Loaded {len(sources)} active sources")

        return sources

    def scrape_source(self, source: Dict) -> List[Dict]:
        """
        Scrape events from a single source

        Args:
            source: Source dictionary

        Returns:
            List of events
        """
        source_id = source.get('source_id', 'unknown')
        source_name = source.get('source_name', 'Unknown')
        source_url = source.get('source_url', '')
        source_type = source.get('source_type', 'Website')

        self.logger.info(f"Scraping {source_name} ({source_type}): {source_url}")

        # Check cache
        cached_events = self.cache_manager.get_cached_source_events(source_id)
        if cached_events:
            return cached_events

        events = []

        try:
            # Initialize scrapers BEFORE health check
            if source_type == 'Facebook':
                if not self.facebook_scraper:
                    if not self.selenium_manager:
                        self.selenium_manager = SeleniumManager(self.config)
                    self.facebook_scraper = FacebookScraper(self.selenium_manager, self.config)
            else:
                if not self.web_scraper:
                    if not self.selenium_manager:
                        self.selenium_manager = SeleniumManager(self.config)
                    self.web_scraper = WebScraper(self.selenium_manager, self.config)

            # Health check (NOW scrapers are initialized)
            if self.config.get('health_check', {}).get('enabled', True):
                if source_type == 'Website':
                    if not self.web_scraper.health_check(source_url):
                        self.logger.warning(f"Health check failed for {source_url}")
                        if self.config['health_check'].get('skip_failed_sources', True):
                            return events

            # Scrape based on type
            if source_type == 'Facebook':
                events = self._scrape_facebook_source(source)
            else:
                events = self._scrape_web_source(source)

            # Add source metadata to events
            for event in events:
                event['source_name'] = source_name
                event['source_url'] = source_url
                event['source_id'] = source_id

            # Cache results
            if events:
                self.cache_manager.cache_source_events(source_id, events)

            self.logger.info(f"✓ {source_name}: {len(events)} events")
            self.stats['sources_scraped'] += 1

        except Exception as e:
            self.logger.error(f"✗ Failed to scrape {source_name}: {e}", exc_info=True)
            self.failed_sources.append({
                'source_id': source_id,
                'source_name': source_name,
                'error': str(e)
            })
            self.stats['sources_failed'] += 1

        return events

    def _scrape_facebook_source(self, source: Dict) -> List[Dict]:
        """
        Scrape Facebook source

        Args:
            source: Source dictionary

        Returns:
            List of events
        """
        # Scraper is already initialized in scrape_source()
        return self.facebook_scraper.scrape_page_events(source['source_url'])

    def _scrape_web_source(self, source: Dict) -> List[Dict]:
        """
        Scrape website source

        Args:
            source: Source dictionary

        Returns:
            List of events
        """
        # Scraper is already initialized in scrape_source()
        # Check if Selenium is required
        use_selenium = source.get('requires_selenium', '').lower() == 'yes'

        return self.web_scraper.scrape_url(source['source_url'], use_selenium=use_selenium)

    def scrape_all_sources(self, sources: List[Dict], max_workers: int = 5):
        """
        Scrape all sources with multi-threading

        Args:
            sources: List of sources
            max_workers: Number of parallel workers
        """
        self.stats['start_time'] = datetime.now()

        self.logger.info(f"Starting scraping with {max_workers} workers")

        # Use ThreadPoolExecutor for parallel scraping
        use_multithreading = self.config.get('performance', {}).get('use_multithreading', True)

        if use_multithreading and max_workers > 1:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_source = {
                    executor.submit(self.scrape_source, source): source
                    for source in sources
                }

                # Progress bar
                with tqdm(total=len(sources), desc="Scraping sources") as pbar:
                    for future in as_completed(future_to_source):
                        source = future_to_source[future]
                        try:
                            events = future.result()
                            self.all_events.extend(events)
                        except Exception as e:
                            self.logger.error(f"Error in thread for {source.get('source_name')}: {e}")

                        pbar.update(1)
        else:
            # Sequential scraping
            for source in tqdm(sources, desc="Scraping sources"):
                events = self.scrape_source(source)
                self.all_events.extend(events)

        self.stats['events_total'] = len(self.all_events)
        self.logger.info(f"Scraping complete: {self.stats['events_total']} events from {len(sources)} sources")

    def process_events(self):
        """
        Process all scraped events (clean, validate, translate, geocode)
        """
        self.logger.info("Processing events...")

        # Process each event
        processed_events = []

        for event in tqdm(self.all_events, desc="Processing events"):
            try:
                # Clean and validate
                event = self.data_processor.process_event(event)

                # Validate
                is_valid, errors = self.data_processor.validate_event(event)
                if is_valid:
                    processed_events.append(event)
                else:
                    self.logger.debug(f"Invalid event: {event.get('title')} - {errors}")

            except Exception as e:
                self.logger.error(f"Error processing event: {e}")

        self.all_events = processed_events
        self.stats['events_valid'] = len(self.all_events)

        self.logger.info(f"Valid events: {self.stats['events_valid']}")

        # Deduplicate
        if self.config.get('data_quality', {}).get('remove_duplicates', True):
            self.logger.info("Removing duplicates...")
            original_count = len(self.all_events)
            self.all_events = self.data_processor.deduplicate_events(self.all_events)
            self.stats['events_duplicates'] = original_count - len(self.all_events)
            self.logger.info(f"Removed {self.stats['events_duplicates']} duplicates")

    def translate_events(self):
        """
        Translate all events to French
        """
        if not self.config.get('translation', {}).get('enabled', True):
            self.logger.info("Translation disabled")
            return

        self.logger.info("Translating events to French...")

        self.all_events = self.translator.translate_batch(self.all_events)
        self.stats['events_translated'] = len(self.all_events)

        self.logger.info(f"Translated {self.stats['events_translated']} events")

    def download_images(self):
        """
        Download and process images for all events
        """
        if not self.config.get('images', {}).get('download_enabled', True):
            self.logger.info("Image downloading disabled")
            return

        self.logger.info("Downloading images...")

        self.all_events = self.image_handler.process_event_images(self.all_events)

        # Count successful downloads
        self.stats['images_downloaded'] = sum(
            1 for event in self.all_events
            if event.get('image_download_success', False)
        )

        self.logger.info(f"Downloaded {self.stats['images_downloaded']} images")

    def export_results(self) -> str:
        """
        Export results to CSV

        Returns:
            Path to exported CSV
        """
        self.logger.info("Exporting to CSV...")

        csv_path = self.csv_exporter.export_to_csv(self.all_events)

        self.logger.info(f"Exported to {csv_path}")

        return csv_path

    def print_summary(self):
        """
        Print scraping summary
        """
        self.stats['end_time'] = datetime.now()
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()

        self.logger.info("="*80)
        self.logger.info("SCRAPING SUMMARY")
        self.logger.info("="*80)
        self.logger.info(f"Duration: {duration:.2f} seconds")
        self.logger.info(f"Sources total: {self.stats['sources_total']}")
        self.logger.info(f"Sources scraped: {self.stats['sources_scraped']}")
        self.logger.info(f"Sources failed: {self.stats['sources_failed']}")
        self.logger.info(f"Events scraped: {self.stats['events_total']}")
        self.logger.info(f"Events valid: {self.stats['events_valid']}")
        self.logger.info(f"Events after dedup: {len(self.all_events)}")
        self.logger.info(f"Duplicates removed: {self.stats['events_duplicates']}")
        self.logger.info(f"Events translated: {self.stats['events_translated']}")
        self.logger.info(f"Images downloaded: {self.stats['images_downloaded']}")
        self.logger.info("="*80)

        # Failed sources
        if self.failed_sources:
            self.logger.warning(f"\nFailed sources ({len(self.failed_sources)}):")
            for failed in self.failed_sources:
                self.logger.warning(f"  - {failed['source_name']}: {failed['error']}")

    def cleanup(self):
        """
        Cleanup resources
        """
        self.logger.info("Cleaning up...")

        if self.selenium_manager:
            self.selenium_manager.close()

        if self.cache_manager:
            self.cache_manager.cleanup_expired()

    def run(self, max_workers: int = 5):
        """
        Run the complete scraping pipeline

        Args:
            max_workers: Number of parallel workers
        """
        try:
            # Load sources
            sources = self.load_sources()

            # Scrape all sources
            self.scrape_all_sources(sources, max_workers=max_workers)

            # Process events
            self.process_events()

            # Translate events
            self.translate_events()

            # Download images
            self.download_images()

            # Export results
            csv_path = self.export_results()

            # Print summary
            self.print_summary()

            self.logger.info(f"\n✓ SUCCESS! Results saved to: {csv_path}")

        except KeyboardInterrupt:
            self.logger.warning("\n\nScraping interrupted by user")
            sys.exit(1)

        except Exception as e:
            self.logger.error(f"\n\n✗ FATAL ERROR: {e}", exc_info=True)
            sys.exit(1)

        finally:
            self.cleanup()


def main():
    """
    Main entry point
    """
    parser = argparse.ArgumentParser(
        description='Live Crete Events Scraper - Scrape 202 event sources'
    )

    parser.add_argument(
        '--config',
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=5,
        help='Number of parallel workers (default: 5)'
    )

    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable caching'
    )

    parser.add_argument(
        '--no-images',
        action='store_true',
        help='Skip image downloading'
    )

    parser.add_argument(
        '--no-translation',
        action='store_true',
        help='Skip translation'
    )

    args = parser.parse_args()

    # Load config
    with open(args.config, 'r') as f:
        config = json.load(f)

    # Apply CLI overrides
    if args.no_cache:
        config['cache']['enabled'] = False

    if args.no_images:
        config['images']['download_enabled'] = False

    if args.no_translation:
        config['translation']['enabled'] = False

    # Save modified config
    with open(args.config, 'w') as f:
        json.dump(config, f, indent=2)

    # Run scraper
    scraper = CreteScraper(args.config)
    scraper.run(max_workers=args.workers)


if __name__ == '__main__':
    main()
