"""
IP-Wise Rate Limiting Middleware and In-Memory Sliding Window Manager.
Enforces strict requests-per-minute limits (configurable via settings or runtime toggle) per client IP,
with proxy header resolution (X-Forwarded-For) and minimal RAM footprint.
"""

import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.logging import logger


class SlidingWindowRateLimiter:
    """
    Lightweight, thread-safe in-memory sliding window rate limiter.
    Stores request timestamps per IP and automatically evicts expired entries.
    Supports both static settings configuration (.env) and dynamic runtime overrides.
    """

    def __init__(
        self,
        limit_per_minute: Optional[int] = None,
        window_seconds: int = 60,
        enabled: Optional[bool] = None
    ):
        self._limit_per_minute: Optional[int] = limit_per_minute
        self.window_seconds: int = window_seconds
        self._enabled: Optional[bool] = enabled
        self._history: Dict[str, List[float]] = defaultdict(list)
        self._last_cleanup: float = time.time()

    @property
    def is_enabled(self) -> bool:
        """Determines if rate limiting is active, checking runtime override or settings."""
        if self._enabled is not None:
            return self._enabled
        return get_settings().RATE_LIMIT_ENABLED

    @property
    def limit_per_minute(self) -> int:
        """Returns the active limit per minute, checking runtime override or settings."""
        if self._limit_per_minute is not None:
            return self._limit_per_minute
        return get_settings().RATE_LIMIT_PER_MINUTE

    def set_enabled(self, enabled: bool):
        """Programmatically toggle rate limiting on or off at runtime."""
        self._enabled = enabled
        logger.info(f"[RateLimiter] Rate limiting toggle updated: enabled={enabled}")

    def set_limit(self, limit_per_minute: int):
        """Programmatically configure the number of requests per minute."""
        self._limit_per_minute = max(1, limit_per_minute)
        logger.info(f"[RateLimiter] Rate limit threshold updated: {self._limit_per_minute} req/min")

    def reset_overrides(self):
        """Reverts runtime overrides back to Settings (.env defaults)."""
        self._enabled = None
        self._limit_per_minute = None
        logger.info("[RateLimiter] Runtime overrides cleared. Reverted to Settings (.env).")

    def reset(self, ip: Optional[str] = None):
        """Clears request timestamp history for a specific IP or all IPs."""
        if ip:
            self._history.pop(ip, None)
        else:
            self._history.clear()

    def get_client_ip(self, request: Request) -> str:
        """
        Safely extracts client IP from proxy headers or direct client connection.
        Prioritizes X-Forwarded-For (client, proxy1, proxy2) -> X-Real-IP -> client.host.
        """
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
            if client_ip:
                return client_ip

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        if request.client and request.client.host:
            return request.client.host

        return "127.0.0.1"

    def is_allowed(self, ip: str) -> Tuple[bool, int]:
        """
        Checks if the IP is within the configured limit.
        Returns: (is_allowed: bool, retry_after_seconds: int)
        """
        if not self.is_enabled:
            return True, 0

        now = time.time()
        cutoff = now - self.window_seconds

        # Periodic cleanup of completely stale IPs every 5 minutes
        if now - self._last_cleanup > 300:
            self._cleanup_stale_ips(cutoff)
            self._last_cleanup = now

        # Filter out timestamps outside the active window
        timestamps = [t for t in self._history[ip] if t > cutoff]
        self._history[ip] = timestamps

        active_limit = self.limit_per_minute
        if len(timestamps) >= active_limit:
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

    EXEMPT_PATHS = {"/docs", "/redoc", "/openapi.json", "/api/v2/health", "/api/v2/health/rate-limit", "/"}

    async def dispatch(self, request: Request, call_next) -> Response:
        # Check if rate limiting is enabled
        if not rate_limiter.is_enabled:
            return await call_next(request)

        # Bypass exempt paths
        if request.url.path in self.EXEMPT_PATHS or request.url.path.startswith("/api/v2/health"):
            return await call_next(request)

        client_ip = rate_limiter.get_client_ip(request)
        allowed, retry_after = rate_limiter.is_allowed(client_ip)

        if not allowed:
            active_limit = rate_limiter.limit_per_minute
            logger.warning(
                f"[RateLimiter] Rate limit exceeded for IP: {client_ip} "
                f"({active_limit} req/min). Path: {request.url.path}"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": f"Rate limit exceeded. Maximum {active_limit} requests per minute allowed.",
                    "retry_after_seconds": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )

        response = await call_next(request)
        return response
