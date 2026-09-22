"""
IP-Wise Rate Limiting Middleware and In-Memory Sliding Window Manager.
Enforces strict requests-per-minute limits (default: 25 req/min) per client IP,
with proxy header resolution (X-Forwarded-For) and minimal RAM footprint.
"""

import time
from collections import defaultdict
from typing import Dict, List, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.logging import logger


class SlidingWindowRateLimiter:
    """
    Lightweight, thread-safe in-memory sliding window rate limiter.
    Stores request timestamps per IP and automatically evicts expired entries.
    """

    def __init__(self, limit_per_minute: int = 25, window_seconds: int = 60):
        self.limit_per_minute = limit_per_minute
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    def get_client_ip(self, request: Request) -> str:
        """
        Safely extracts client IP from proxy headers or direct client connection.
        Prioritizes X-Forwarded-For (client, proxy1, proxy2) -> X-Real-IP -> client.host.
        """
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # First element in comma-separated list is the original client IP
            client_ip = forwarded_for.split(",")[0].strip()
            if client_ip:
                return client_ip

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        if request.client and request.client.host:
            return request.client.host

        return "127.0.0.1"

    def is_allowed(self, ip: str) -> tuple[bool, int]:
        """
        Checks if the IP is within limits.
        Returns: (is_allowed: bool, retry_after_seconds: int)
        """
        now = time.time()
        cutoff = now - self.window_seconds

        # Periodic cleanup of completely stale IPs every 5 minutes
        if now - self._last_cleanup > 300:
            self._cleanup_stale_ips(cutoff)
            self._last_cleanup = now

        # Filter out timestamps outside the active window
        timestamps = [t for t in self._history[ip] if t > cutoff]
        self._history[ip] = timestamps

        if len(timestamps) >= self.limit_per_minute:
            oldest = timestamps[0]
            retry_after = max(1, int(self.window_seconds - (now - oldest)))
            return False, retry_after

        # Record this request
        self._history[ip].append(now)
        return True, 0

    def _cleanup_stale_ips(self, cutoff: float):
        """Purges IP keys that have zero active timestamps to bound memory."""
        stale_keys = [ip for ip, ts in self._history.items() if not ts or ts[-1] <= cutoff]
        for ip in stale_keys:
            del self._history[ip]


# Singleton instance
rate_limiter = SlidingWindowRateLimiter()


class IPRateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette middleware enforcing IP-wise rate limits.
    Bypasses documentation, OpenAPI schema, and health check endpoints.
    """

    EXEMPT_PATHS = {"/docs", "/redoc", "/openapi.json", "/api/v2/health", "/"}

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()

        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Bypass exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Dynamic limit sync from settings
        rate_limiter.limit_per_minute = settings.RATE_LIMIT_PER_MINUTE

        client_ip = rate_limiter.get_client_ip(request)
        allowed, retry_after = rate_limiter.is_allowed(client_ip)

        if not allowed:
            logger.warning(
                f"[RateLimiter] Rate limit exceeded for IP: {client_ip} "
                f"({settings.RATE_LIMIT_PER_MINUTE} req/min). Path: {request.url.path}"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": f"Rate limit exceeded. Maximum {settings.RATE_LIMIT_PER_MINUTE} requests per minute allowed.",
                    "retry_after_seconds": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )

        response = await call_next(request)
        return response
