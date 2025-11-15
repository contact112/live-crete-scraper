"""
Cache Manager
Manages caching and retry logic for scraping operations
"""

import logging
import time
import json
import hashlib
from pathlib import Path
from typing import Any, Optional, Callable, Dict
from datetime import datetime, timedelta
from functools import wraps

import diskcache


class CacheManager:
    """
    Manages caching and retry operations
    """

    def __init__(self, config: Dict):
        """
        Initialize Cache Manager

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.cache_config = config.get('cache', {})
        self.retry_config = config.get('retry', {})

        # Initialize cache
        if self.cache_config.get('enabled', True):
            paths = config.get('paths', {})
            cache_dir = Path(paths.get('cache_dir', 'data/cache'))
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Get cache size limit
            size_limit = self.cache_config.get('cache_max_size_mb', 500) * 1024 * 1024

            self.cache = diskcache.Cache(
                str(cache_dir),
                size_limit=size_limit
            )
        else:
            self.cache = None

        # TTL
        self.ttl_hours = self.cache_config.get('cache_ttl_hours', 24)
        self.ttl_seconds = self.ttl_hours * 3600

        # Retry settings
        self.max_retries = self.retry_config.get('max_retries', 3)
        self.backoff_factor = self.retry_config.get('backoff_factor', 2)
        self.initial_backoff = self.retry_config.get('initial_backoff', 2)
        self.max_backoff = self.retry_config.get('max_backoff', 60)

        self.logger.info(f"Cache manager initialized (enabled: {self.cache is not None})")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        if not self.cache:
            return default

        try:
            value = self.cache.get(key, default=default)
            if value is not default:
                self.logger.debug(f"Cache hit: {key}")
            return value
        except Exception as e:
            self.logger.error(f"Cache get error: {e}")
            return default

    def set(self, key: str, value: Any, expire: Optional[int] = None):
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            expire: Expiration time in seconds (uses default TTL if None)
        """
        if not self.cache:
            return

        try:
            if expire is None:
                expire = self.ttl_seconds

            self.cache.set(key, value, expire=expire)
            self.logger.debug(f"Cache set: {key} (expire: {expire}s)")
        except Exception as e:
            self.logger.error(f"Cache set error: {e}")

    def delete(self, key: str):
        """
        Delete key from cache

        Args:
            key: Cache key
        """
        if not self.cache:
            return

        try:
            self.cache.delete(key)
            self.logger.debug(f"Cache delete: {key}")
        except Exception as e:
            self.logger.error(f"Cache delete error: {e}")

    def clear(self):
        """
        Clear all cache
        """
        if not self.cache:
            return

        try:
            self.cache.clear()
            self.logger.info("Cache cleared")
        except Exception as e:
            self.logger.error(f"Cache clear error: {e}")

    def generate_key(self, *args, **kwargs) -> str:
        """
        Generate cache key from arguments

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Cache key string
        """
        # Create string representation
        key_parts = [str(arg) for arg in args]
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_str = '|'.join(key_parts)

        # Hash for consistent length
        key_hash = hashlib.md5(key_str.encode()).hexdigest()

        return key_hash

    def cached(self, expire: Optional[int] = None):
        """
        Decorator for caching function results

        Args:
            expire: Cache expiration in seconds

        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = f"{func.__name__}:{self.generate_key(*args, **kwargs)}"

                # Try to get from cache
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    self.logger.debug(f"Using cached result for {func.__name__}")
                    return cached_value

                # Execute function
                result = func(*args, **kwargs)

                # Cache result
                if result is not None:
                    self.set(cache_key, result, expire=expire)

                return result

            return wrapper
        return decorator

    def retry_on_failure(
        self,
        max_retries: Optional[int] = None,
        backoff_factor: Optional[float] = None,
        retry_on_exceptions: tuple = (Exception,)
    ):
        """
        Decorator for retrying failed operations with exponential backoff

        Args:
            max_retries: Maximum number of retries
            backoff_factor: Backoff multiplication factor
            retry_on_exceptions: Tuple of exceptions to retry on

        Returns:
            Decorated function
        """
        if max_retries is None:
            max_retries = self.max_retries
        if backoff_factor is None:
            backoff_factor = self.backoff_factor

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None

                for attempt in range(max_retries + 1):
                    try:
                        # Execute function
                        result = func(*args, **kwargs)
                        return result

                    except retry_on_exceptions as e:
                        last_exception = e

                        if attempt < max_retries:
                            # Calculate backoff time
                            backoff_time = min(
                                self.initial_backoff * (backoff_factor ** attempt),
                                self.max_backoff
                            )

                            self.logger.warning(
                                f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                                f"Retrying in {backoff_time:.1f}s..."
                            )

                            time.sleep(backoff_time)
                        else:
                            self.logger.error(
                                f"{func.__name__} failed after {max_retries + 1} attempts: {e}"
                            )

                # All retries failed
                if last_exception:
                    raise last_exception

            return wrapper
        return decorator

    def retry_with_cache(
        self,
        expire: Optional[int] = None,
        max_retries: Optional[int] = None
    ):
        """
        Combined decorator for caching and retry

        Args:
            expire: Cache expiration
            max_retries: Maximum retries

        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            # Apply retry first, then cache
            func_with_retry = self.retry_on_failure(max_retries=max_retries)(func)
            func_with_cache = self.cached(expire=expire)(func_with_retry)
            return func_with_cache
        return decorator

    def cache_url_response(
        self,
        url: str,
        response_data: Any,
        expire: Optional[int] = None
    ):
        """
        Cache URL response

        Args:
            url: URL
            response_data: Response data to cache
            expire: Expiration time
        """
        cache_key = f"url:{self.generate_key(url)}"
        self.set(cache_key, response_data, expire=expire)

    def get_cached_url_response(self, url: str) -> Optional[Any]:
        """
        Get cached URL response

        Args:
            url: URL

        Returns:
            Cached response or None
        """
        cache_key = f"url:{self.generate_key(url)}"
        return self.get(cache_key)

    def cache_source_events(
        self,
        source_id: str,
        events: list,
        expire: Optional[int] = None
    ):
        """
        Cache events from a source

        Args:
            source_id: Source identifier
            events: List of events
            expire: Expiration time
        """
        cache_key = f"source:{source_id}"
        cache_data = {
            'events': events,
            'cached_at': datetime.now().isoformat(),
            'count': len(events)
        }
        self.set(cache_key, cache_data, expire=expire)

    def get_cached_source_events(self, source_id: str) -> Optional[list]:
        """
        Get cached events from a source

        Args:
            source_id: Source identifier

        Returns:
            List of cached events or None
        """
        cache_key = f"source:{source_id}"
        cache_data = self.get(cache_key)

        if cache_data and isinstance(cache_data, dict):
            cached_at = datetime.fromisoformat(cache_data.get('cached_at', ''))
            age_hours = (datetime.now() - cached_at).total_seconds() / 3600

            self.logger.info(
                f"Using cached events for {source_id} "
                f"({cache_data.get('count', 0)} events, {age_hours:.1f}h old)"
            )

            return cache_data.get('events', [])

        return None

    def get_stats(self) -> Dict:
        """
        Get cache statistics

        Returns:
            Dictionary with cache stats
        """
        if not self.cache:
            return {'enabled': False}

        stats = {
            'enabled': True,
            'size': len(self.cache),
            'volume': self.cache.volume(),
            'ttl_hours': self.ttl_hours
        }

        return stats

    def cleanup_expired(self):
        """
        Clean up expired cache entries
        """
        if not self.cache:
            return

        try:
            # diskcache handles expiration automatically
            # But we can manually check and report
            initial_size = len(self.cache)
            self.cache.cull()
            final_size = len(self.cache)

            removed = initial_size - final_size
            if removed > 0:
                self.logger.info(f"Cleaned up {removed} expired cache entries")

        except Exception as e:
            self.logger.error(f"Cache cleanup error: {e}")

    def save_checkpoint(self, checkpoint_id: str, data: Dict):
        """
        Save scraping checkpoint for recovery

        Args:
            checkpoint_id: Checkpoint identifier
            data: Checkpoint data
        """
        cache_key = f"checkpoint:{checkpoint_id}"
        checkpoint_data = {
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        # Checkpoints don't expire
        self.set(cache_key, checkpoint_data, expire=None)
        self.logger.info(f"Checkpoint saved: {checkpoint_id}")

    def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict]:
        """
        Load scraping checkpoint

        Args:
            checkpoint_id: Checkpoint identifier

        Returns:
            Checkpoint data or None
        """
        cache_key = f"checkpoint:{checkpoint_id}"
        checkpoint_data = self.get(cache_key)

        if checkpoint_data and isinstance(checkpoint_data, dict):
            self.logger.info(
                f"Checkpoint loaded: {checkpoint_id} "
                f"(saved at {checkpoint_data.get('timestamp', 'unknown')})"
            )
            return checkpoint_data.get('data')

        return None

    def delete_checkpoint(self, checkpoint_id: str):
        """
        Delete checkpoint

        Args:
            checkpoint_id: Checkpoint identifier
        """
        cache_key = f"checkpoint:{checkpoint_id}"
        self.delete(cache_key)
        self.logger.info(f"Checkpoint deleted: {checkpoint_id}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.cache:
            self.cache.close()
