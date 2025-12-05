
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


class SimpleCache:

    def __init__(self):
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._default_ttl = timedelta(minutes=5)
        self._lock = threading.RLock()
        self._last_cleanup = datetime.now(timezone.utc)

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None

            value, expiry = self._cache[key]
            if datetime.now(timezone.utc) > expiry:
                del self._cache[key]
                return None

            return value

    def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> None:
        if ttl is None:
            ttl = self._default_ttl

        with self._lock:
            expiry = datetime.now(timezone.utc) + ttl
            self._cache[key] = (value, expiry)
            self._cleanup_if_needed()

    def delete(self, key: str) -> None:
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._last_cleanup = datetime.now(timezone.utc)

    def get_or_set(
        self,
        key: str,
        factory_func: callable,
        ttl: Optional[timedelta] = None,
    ) -> Any:
        value = self.get(key)
        if value is not None:
            return value

        value = factory_func()
        self.set(key, value, ttl)
        return value

    def _cleanup_if_needed(self) -> None:
        now = datetime.now(timezone.utc)
        cleanup_interval = timedelta(minutes=5)

        if now - self._last_cleanup < cleanup_interval:
            return


        expired_keys = [key for key, (_, expiry) in self._cache.items() if now > expiry]
        for key in expired_keys:
            del self._cache[key]

        self._last_cleanup = now


cache = SimpleCache()
