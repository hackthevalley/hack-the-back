
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


class SimpleCache:

    def __init__(self):
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._default_ttl = timedelta(minutes=5)

    def get(self, key: str) -> Optional[Any]:
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

        expiry = datetime.now(timezone.utc) + ttl
        self._cache[key] = (value, expiry)

    def delete(self, key: str) -> None:
        if key in self._cache:
            del self._cache[key]

    def clear(self) -> None:
        self._cache.clear()

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



cache = SimpleCache()
