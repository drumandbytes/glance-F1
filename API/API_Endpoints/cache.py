import asyncio
from typing import Any, Optional

class InMemoryCache:
    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key in self._store:
                value, expiry = self._store[key]
                if expiry > asyncio.get_event_loop().time():
                    return value
                del self._store[key]
            return None

    async def set(self, key: str, value: Any, expire: int = 600) -> None:
        async with self._lock:
            loop = asyncio.get_event_loop()
            self._store[key] = (value, loop.time() + expire)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)


cache_manager = InMemoryCache()
