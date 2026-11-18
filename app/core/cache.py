"""
Lightweight Async TTL Cache.
Supports optional Redis backend when REDIS_URL is configured and the `redis` package
is installed, falling back transparently to a bounded in-memory TTL cache (<5 MB RAM).
"""

import asyncio
import json
import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple


class AsyncTTLCache:
    """Bounded async TTL cache with optional Redis write-through/read-through."""

    def __init__(self, namespace: str, max_entries: int = 512, redis_url: Optional[str] = None):
        self.namespace = namespace
        self.max_entries = max_entries
        self.redis_url = redis_url
        self._store: OrderedDict[str, Tuple[float, Any]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._redis_client: Any = None
        self._redis_checked = False
        self.hits = 0
        self.misses = 0

    async def _get_redis(self) -> Any:
        if self._redis_checked:
            return self._redis_client
        self._redis_checked = True
        if not self.redis_url:
            return None
        try:
            import redis.asyncio as aioredis  # type: ignore
            self._redis_client = aioredis.from_url(self.redis_url, decode_responses=True)
        except Exception:
            self._redis_client = None
        return self._redis_client

    def _rkey(self, key: str) -> str:
        return f"marketmind:{self.namespace}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        now = time.monotonic()
        async with self._lock:
            item = self._store.get(key)
            if item is not None:
                expires_at, val = item
                if expires_at > now:
                    self._store.move_to_end(key)
                    self.hits += 1
                    return val
                del self._store[key]

        redis_client = await self._get_redis()
        if redis_client is not None:
            try:
                raw = await redis_client.get(self._rkey(key))
                if raw is not None:
                    val = json.loads(raw)
                    self.hits += 1
                    return val
            except Exception:
                pass

        self.misses += 1
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        expires_at = time.monotonic() + ttl_seconds
        async with self._lock:
            self._store[key] = (expires_at, value)
            self._store.move_to_end(key)
            while len(self._store) > self.max_entries:
                self._store.popitem(last=False)

        redis_client = await self._get_redis()
        if redis_client is not None:
            try:
                await redis_client.setex(self._rkey(key), ttl_seconds, json.dumps(value))
            except Exception:
                pass

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()
            self.hits = 0
            self.misses = 0

    def stats(self) -> Dict[str, Any]:
        return {
            "namespace": self.namespace,
            "entries": len(self._store),
            "hits": self.hits,
            "misses": self.misses,
            "backend": "redis+memory" if self._redis_client is not None else "memory",
        }


_CACHES: Dict[str, AsyncTTLCache] = {}


def get_ttl_cache(namespace: str, max_entries: int = 512, redis_url: Optional[str] = None) -> AsyncTTLCache:
    if namespace not in _CACHES:
        _CACHES[namespace] = AsyncTTLCache(namespace=namespace, max_entries=max_entries, redis_url=redis_url)
    return _CACHES[namespace]


async def clear_all_ttl_caches() -> None:
    for cache in _CACHES.values():
        await cache.clear()
