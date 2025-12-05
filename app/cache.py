"""
Simple in-memory caching for frequently accessed data.

This module provides caching for static/semi-static data that doesn't change
frequently during runtime to reduce database queries.
"""

import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


class SimpleCache:
    """Thread-safe simple in-memory cache with TTL support."""

    def __init__(self):
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._default_ttl = timedelta(minutes=5)
        self._lock = threading.RLock()
        self._last_cleanup = datetime.now(timezone.utc)

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if it exists and hasn't expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                return None

            value, expiry = self._cache[key]
            if datetime.now(timezone.utc) > expiry:
                del self._cache[key]
                return None

            return value

    def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> None:
        """
        Set value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live (default: 5 minutes)
        """
        if ttl is None:
            ttl = self._default_ttl

        with self._lock:
            expiry = datetime.now(timezone.utc) + ttl
            self._cache[key] = (value, expiry)
            self._cleanup_if_needed()

    def delete(self, key: str) -> None:
        """
        Delete a key from cache.

        Args:
            key: Cache key to delete
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self) -> None:
        """Clear all cached items."""
        with self._lock:
            self._cache.clear()
            self._last_cleanup = datetime.now(timezone.utc)

    def get_or_set(
        self,
        key: str,
        factory_func: callable,
        ttl: Optional[timedelta] = None,
    ) -> Any:
        """
        Get value from cache or compute it using factory function.

        Args:
            key: Cache key
            factory_func: Function to compute value if not in cache
            ttl: Time to live for new values

        Returns:
            Cached or computed value
        """
        value = self.get(key)
        if value is not None:
            return value

        value = factory_func()
        self.set(key, value, ttl)
        return value

    def _cleanup_if_needed(self) -> None:
        """
        Periodically clean up expired entries to prevent memory leaks.

        Runs cleanup every 5 minutes to remove expired entries that were never
        accessed again. This prevents unbounded memory growth.

        Note: This method assumes the lock is already held by the caller.
        """
        now = datetime.now(timezone.utc)
        cleanup_interval = timedelta(minutes=5)

        if now - self._last_cleanup < cleanup_interval:
            return

        # Remove all expired entries
        expired_keys = [key for key, (_, expiry) in self._cache.items() if now > expiry]
        for key in expired_keys:
            del self._cache[key]

        self._last_cleanup = now


cache = SimpleCache()
