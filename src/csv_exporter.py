"""
CSV Exporter
Exports event data to CSV format with all required columns
"""

import logging
import csv
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class CSVExporter:
    """
    Exports events to CSV format
    """

    # CSV column definitions (38 original + 10 translated = 48 columns)
    COLUMNS = [
        # Original columns (38)
        'event_id',
        'title',
        'subtitle',
        'description',
        'excerpt',
        'start_date',
        'end_date',
        'all_day',
        'timezone',
        'venue_name',
        'venue_address',
        'venue_city',
        'venue_region',
        'venue_postal_code',
        'venue_country',
        'venue_latitude',
        'venue_longitude',
        'organizer_name',
        'organizer_email',
        'organizer_phone',
        'organizer_website',
        'category',
        'tags',
        'event_type',
        'image_url',
        'image_local_path',
        'thumbnail_path',
        'gallery_urls',
        'price',
        'booking_url',
        'capacity',
        'language',
        'source_url',
        'source_name',
        'scraped_date',
        'last_updated',
        'slug',
        'featured',
        'status',
        # Translated columns (10)
        'title_fr',
        'subtitle_fr',
        'description_fr',
        'excerpt_fr',
        'venue_name_fr',
        'venue_address_fr',
        'venue_city_fr',
        'organizer_name_fr',
        'category_fr',
        'tags_fr'
    ]

    def __init__(self, config: Dict):
        """
        Initialize CSV Exporter

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.export_config = config.get('export', {})

        # Paths
        paths = config.get('paths', {})
        self.output_dir = Path(paths.get('output_dir', 'data/output'))
        self.backup_dir = Path(paths.get('backup_dir', 'data/backups'))

        # Ensure directories exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info("CSV Exporter initialized")

    def export_to_csv(
        self,
        events: List[Dict],
        filename: Optional[str] = None
    ) -> str:
        """
        Export events to CSV file

        Args:
            events: List of event dictionaries
            filename: Output filename (auto-generated if None)

        Returns:
            Path to created CSV file
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = self.export_config.get('output_filename', 'crete_events_{timestamp}.csv')
            filename = filename.format(timestamp=timestamp)

        output_path = self.output_dir / filename

        try:
            self.logger.info(f"Exporting {len(events)} events to {output_path}")

            # Prepare data
            rows = []
            for event in events:
                row = self._event_to_row(event)
                rows.append(row)

            # Write CSV
            encoding = self.export_config.get('encoding', 'utf-8')
            separator = self.export_config.get('separator', ',')

            with open(output_path, 'w', encoding=encoding, newline='') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=self.COLUMNS,
                    delimiter=separator,
                    quoting=csv.QUOTE_MINIMAL,
                    extrasaction='ignore'
                )

                if self.export_config.get('include_header', True):
                    writer.writeheader()

                writer.writerows(rows)

            self.logger.info(f"Successfully exported to {output_path}")

            # Backup raw data
            if self.export_config.get('backup_raw_data', True):
                self._backup_raw_data(events)

            return str(output_path)

        except Exception as e:
            self.logger.error(f"Failed to export CSV: {e}")
            raise

    def _event_to_row(self, event: Dict) -> Dict:
        """
        Convert event dictionary to CSV row

        Args:
            event: Event dictionary

        Returns:
            Row dictionary with all columns
        """
        row = {}

        for column in self.COLUMNS:
            value = event.get(column)

            # Handle different data types
            if value is None or value == '':
                row[column] = ''
            elif isinstance(value, (list, dict)):
                # Convert lists and dicts to JSON strings
                row[column] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, bool):
                # Convert boolean to string
                row[column] = 'yes' if value else 'no'
            elif isinstance(value, (int, float)):
                # Keep numbers as is
                row[column] = str(value)
            else:
                # String value - escape if needed
                row[column] = str(value)

        # Handle image paths
        if event.get('image_full_path'):
            row['image_local_path'] = event['image_full_path']
        if event.get('image_thumbnail_path'):
            row['thumbnail_path'] = event['image_thumbnail_path']

        # Ensure all columns exist
        for column in self.COLUMNS:
            if column not in row:
                row[column] = ''

        return row

    def _backup_raw_data(self, events: List[Dict]):
        """
        Backup raw event data as JSON

        Args:
            events: List of events
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f'events_backup_{timestamp}.json'
            backup_path = self.backup_dir / backup_filename

            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(events, f, ensure_ascii=False, indent=2)

            # Compress if configured
            if self.export_config.get('compress_backups', True):
                self._compress_file(backup_path)

            self.logger.info(f"Raw data backed up to {backup_path}")

        except Exception as e:
            self.logger.error(f"Failed to backup raw data: {e}")

    def _compress_file(self, filepath: Path):
        """
        Compress file using gzip

        Args:
            filepath: Path to file to compress
        """
        try:
            import gzip
            import shutil

            gz_path = filepath.with_suffix(filepath.suffix + '.gz')

            with open(filepath, 'rb') as f_in:
                with gzip.open(gz_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Remove original file
            filepath.unlink()

            self.logger.debug(f"Compressed {filepath} to {gz_path}")

        except Exception as e:
            self.logger.error(f"Failed to compress file: {e}")

    def import_from_csv(self, filepath: str) -> List[Dict]:
        """
        Import events from CSV file

        Args:
            filepath: Path to CSV file

        Returns:
            List of event dictionaries
        """
        events = []

        try:
            self.logger.info(f"Importing events from {filepath}")

            encoding = self.export_config.get('encoding', 'utf-8')
            separator = self.export_config.get('separator', ',')

            with open(filepath, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f, delimiter=separator)

                for row in reader:
                    event = self._row_to_event(row)
                    events.append(event)

            self.logger.info(f"Imported {len(events)} events from {filepath}")

        except Exception as e:
            self.logger.error(f"Failed to import CSV: {e}")
            raise

        return events

    def _row_to_event(self, row: Dict) -> Dict:
        """
        Convert CSV row to event dictionary

        Args:
            row: CSV row dictionary

        Returns:
            Event dictionary
        """
        event = {}

        for column, value in row.items():
            # Skip empty values
            if value == '':
                event[column] = None
                continue

            # Parse JSON fields
            if column in ['tags', 'gallery_urls', 'tags_fr']:
                try:
                    event[column] = json.loads(value)
                except:
                    event[column] = value

            # Parse boolean fields
            elif column in ['all_day', 'featured']:
                event[column] = value.lower() in ['yes', 'true', '1']

            # Parse numeric fields
            elif column in ['venue_latitude', 'venue_longitude', 'price', 'capacity']:
                try:
                    if '.' in value:
                        event[column] = float(value)
                    else:
                        event[column] = int(value)
                except:
                    event[column] = value

            else:
                event[column] = value

        return event

    def export_sample(self, events: List[Dict], sample_size: int = 10) -> str:
        """
        Export a sample of events for testing

        Args:
            events: List of events
            sample_size: Number of events to export

        Returns:
            Path to sample CSV
        """
        sample_events = events[:sample_size]
        filename = f'sample_{sample_size}_events.csv'

        return self.export_to_csv(sample_events, filename)

    def get_export_stats(self) -> Dict:
        """
        Get export statistics

        Returns:
            Dictionary with export stats
        """
        stats = {
            'output_files': len(list(self.output_dir.glob('*.csv'))),
            'backup_files': len(list(self.backup_dir.glob('*.json*'))),
            'total_output_size_mb': 0,
            'total_backup_size_mb': 0
        }

        # Calculate sizes
        for csv_file in self.output_dir.glob('*.csv'):
            stats['total_output_size_mb'] += csv_file.stat().st_size / (1024 * 1024)

        for backup_file in self.backup_dir.glob('*.json*'):
            stats['total_backup_size_mb'] += backup_file.stat().st_size / (1024 * 1024)

        stats['total_output_size_mb'] = round(stats['total_output_size_mb'], 2)
        stats['total_backup_size_mb'] = round(stats['total_backup_size_mb'], 2)

        return stats

    def merge_csv_files(self, output_filename: str = 'merged_events.csv') -> str:
        """
        Merge all CSV files in output directory

        Args:
            output_filename: Name for merged file

        Returns:
            Path to merged CSV
        """
        all_events = []

        # Read all CSV files
        for csv_file in self.output_dir.glob('*.csv'):
            if csv_file.name == output_filename:
                continue

            try:
                events = self.import_from_csv(str(csv_file))
                all_events.extend(events)
                self.logger.debug(f"Loaded {len(events)} events from {csv_file.name}")
            except Exception as e:
                self.logger.error(f"Failed to read {csv_file}: {e}")

        # Export merged
        if all_events:
            merged_path = self.export_to_csv(all_events, output_filename)
            self.logger.info(f"Merged {len(all_events)} events into {merged_path}")
            return merged_path
        else:
            self.logger.warning("No events to merge")
            return ""

    def cleanup_old_exports(self, days: int = 30):
        """
        Remove export files older than specified days

        Args:
            days: Age threshold in days
        """
        import time
        threshold = time.time() - (days * 24 * 60 * 60)

        removed_count = 0

        for directory in [self.output_dir, self.backup_dir]:
            for file in directory.glob('*'):
                if file.stat().st_mtime < threshold:
                    try:
                        file.unlink()
                        removed_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to remove {file}: {e}")

        self.logger.info(f"Removed {removed_count} old export files")
