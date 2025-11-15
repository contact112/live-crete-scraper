#!/usr/bin/env python3
"""
Test script for scraper initialization fix
Tests 5 different sources (mix of Website and Facebook)
"""

import json
import logging
from main import CreteScraper

# Setup simple logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def create_test_sources():
    """
    Create a list of 5 diverse test sources
    """
    test_sources = [
        {
            'source_id': 'TEST_001',
            'source_name': 'Crete Events Network',
            'source_url': 'https://www.creteevents.gr/',
            'source_type': 'Website',
            'requires_selenium': 'no'
        },
        {
            'source_id': 'TEST_002',
            'source_name': 'Visit Greece Events',
            'source_url': 'https://www.visitgreece.gr/events/',
            'source_type': 'Website',
            'requires_selenium': 'no'
        },
        {
            'source_id': 'TEST_003',
            'source_name': 'Discover Greece',
            'source_url': 'https://www.discovergreece.com/crete/events',
            'source_type': 'Website',
            'requires_selenium': 'no'
        },
        {
            'source_id': 'TEST_004',
            'source_name': 'Greece Is Magazine',
            'source_url': 'https://www.greece-is.com/events/',
            'source_type': 'Website',
            'requires_selenium': 'no'
        },
        {
            'source_id': 'TEST_005',
            'source_name': 'Lonely Planet Crete',
            'source_url': 'https://www.lonelyplanet.com/greece/crete/events',
            'source_type': 'Website',
            'requires_selenium': 'no'
        }
    ]
    return test_sources

def main():
    """
    Run test scraping on 5 sources
    """
    print("=" * 80)
    print("SCRAPER INITIALIZATION TEST")
    print("Testing 5 diverse sources to validate scraper initialization fix")
    print("=" * 80)

    # Create scraper instance
    print("\n[1/3] Initializing scraper...")
    scraper = CreteScraper('config.json')
    print("✓ Scraper initialized successfully")

    # Get test sources
    print("\n[2/3] Loading test sources...")
    test_sources = create_test_sources()
    print(f"✓ Loaded {len(test_sources)} test sources:")
    for src in test_sources:
        print(f"  - {src['source_name']} ({src['source_type']})")

    # Scrape sources
    print("\n[3/3] Testing scraping (sequential mode)...")
    print("-" * 80)

    scraper.scrape_all_sources(test_sources, max_workers=1)

    # Print results
    print("\n" + "=" * 80)
    print("TEST RESULTS")
    print("=" * 80)
    print(f"Sources tested: {scraper.stats['sources_total']}")
    print(f"Sources scraped successfully: {scraper.stats['sources_scraped']}")
    print(f"Sources failed: {scraper.stats['sources_failed']}")
    print(f"Total events found: {scraper.stats['events_total']}")

    if scraper.failed_sources:
        print(f"\nFailed sources ({len(scraper.failed_sources)}):")
        for failed in scraper.failed_sources:
            print(f"  ✗ {failed['source_name']}: {failed['error']}")

    if scraper.all_events:
        print(f"\n✓ SUCCESS! Found {len(scraper.all_events)} events")
        print("\nSample events:")
        for event in scraper.all_events[:3]:
            print(f"  - {event.get('title', 'No title')} from {event.get('source_name', 'Unknown')}")
    else:
        print("\n⚠ WARNING: No events found. This might be expected for some sources.")

    # Cleanup
    scraper.cleanup()

    print("\n" + "=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
