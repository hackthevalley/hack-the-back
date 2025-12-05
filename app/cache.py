"""
Simple in-memory caching for frequently accessed data.

This module provides caching for static/semi-static data that doesn't change
frequently during runtime to reduce database queries.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional


class SimpleCache:
    """Thread-safe simple in-memory cache with TTL support."""

    def __init__(self):
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._default_ttl = timedelta(minutes=5)

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if it exists and hasn't expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            return None

        value, expiry = self._cache[key]
        if datetime.now(timezone.utc) > expiry:
            # Expired, remove from cache
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

        expiry = datetime.now(timezone.utc) + ttl
        self._cache[key] = (value, expiry)

    def delete(self, key: str) -> None:
        """
        Delete a key from cache.

        Args:
            key: Cache key to delete
        """
        if key in self._cache:
            del self._cache[key]

    def clear(self) -> None:
        """Clear all cached items."""
        self._cache.clear()

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


# Global cache instance
cache = SimpleCache()
