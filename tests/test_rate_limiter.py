"""
Unit & Integration Tests for Sliding-Window IP Rate Limiter and Middleware.
"""

import time
import pytest
import httpx
from starlette.requests import Request

from app.core.rate_limiter import SlidingWindowRateLimiter, rate_limiter, IPRateLimitMiddleware
from app.main import app


def test_sliding_window_allows_under_limit():
    limiter = SlidingWindowRateLimiter(limit_per_minute=3, window_seconds=60, enabled=True)
    ip = "192.168.1.100"

    allowed, retry_after = limiter.is_allowed(ip)
    assert allowed is True
    assert retry_after == 0

    allowed, retry_after = limiter.is_allowed(ip)
    assert allowed is True

    allowed, retry_after = limiter.is_allowed(ip)
    assert allowed is True


def test_sliding_window_blocks_over_limit():
    limiter = SlidingWindowRateLimiter(limit_per_minute=2, window_seconds=60, enabled=True)
    ip = "192.168.1.101"

    # First 2 allowed
    assert limiter.is_allowed(ip)[0] is True
    assert limiter.is_allowed(ip)[0] is True

    # 3rd blocked
    allowed, retry_after = limiter.is_allowed(ip)
    assert allowed is False
    assert 0 < retry_after <= 60


def test_ip_isolation():
    limiter = SlidingWindowRateLimiter(limit_per_minute=1, window_seconds=60, enabled=True)
    ip1 = "10.0.0.1"
    ip2 = "10.0.0.2"

    # IP1 reaches limit
    assert limiter.is_allowed(ip1)[0] is True
    assert limiter.is_allowed(ip1)[0] is False

    # IP2 is still allowed
    assert limiter.is_allowed(ip2)[0] is True
    assert limiter.is_allowed(ip2)[0] is False


def test_runtime_toggle_enable_disable():
    limiter = SlidingWindowRateLimiter(limit_per_minute=1, window_seconds=60, enabled=True)
    ip = "10.0.0.3"

    assert limiter.is_allowed(ip)[0] is True
    assert limiter.is_allowed(ip)[0] is False

    # Disable rate limiter
    limiter.set_enabled(False)
    assert limiter.is_enabled is False
    assert limiter.is_allowed(ip)[0] is True
    assert limiter.is_allowed(ip)[0] is True

    # Re-enable rate limiter
    limiter.set_enabled(True)
    assert limiter.is_enabled is True
    assert limiter.is_allowed(ip)[0] is False


def test_runtime_limit_change():
    limiter = SlidingWindowRateLimiter(limit_per_minute=1, window_seconds=60, enabled=True)
    ip = "10.0.0.4"

    assert limiter.is_allowed(ip)[0] is True
    assert limiter.is_allowed(ip)[0] is False

    # Increase limit to 3
    limiter.set_limit(3)
    assert limiter.limit_per_minute == 3
    assert limiter.is_allowed(ip)[0] is True   # request 2 allowed
    assert limiter.is_allowed(ip)[0] is True   # request 3 allowed
    assert limiter.is_allowed(ip)[0] is False  # request 4 blocked


def test_reset_history():
    limiter = SlidingWindowRateLimiter(limit_per_minute=1, window_seconds=60, enabled=True)
    ip1 = "10.0.0.5"
    ip2 = "10.0.0.6"

    assert limiter.is_allowed(ip1)[0] is True
    assert limiter.is_allowed(ip2)[0] is True
    assert limiter.is_allowed(ip1)[0] is False
    assert limiter.is_allowed(ip2)[0] is False

    # Reset single IP
    limiter.reset(ip1)
    assert limiter.is_allowed(ip1)[0] is True
    assert limiter.is_allowed(ip2)[0] is False

    # Reset all IPs
    limiter.reset()
    assert limiter.is_allowed(ip2)[0] is True


def test_client_ip_extraction_forwarded_for():
    limiter = SlidingWindowRateLimiter()

    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"203.0.113.195, 70.41.3.18")],
        "client": ("127.0.0.1", 12345),
    }
    req = Request(scope)
    assert limiter.get_client_ip(req) == "203.0.113.195"


def test_client_ip_extraction_real_ip():
    limiter = SlidingWindowRateLimiter()

    scope = {
        "type": "http",
        "headers": [(b"x-real-ip", b"198.51.100.42")],
        "client": ("127.0.0.1", 12345),
    }
    req = Request(scope)
    assert limiter.get_client_ip(req) == "198.51.100.42"


@pytest.mark.asyncio
async def test_middleware_blocks_at_runtime_and_exempts_health():
    # Save original state
    orig_enabled = rate_limiter.is_enabled
    orig_limit = rate_limiter.limit_per_minute
    rate_limiter.reset()

    try:
        rate_limiter.set_enabled(True)
        rate_limiter.set_limit(2)

        transport = httpx.ASGITransport(app=app)
        test_ip = "192.0.2.1"
        headers = {"X-Forwarded-For": test_ip}

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. First 2 requests to /api/v2/chat/sessions succeed
            r1 = await client.get("/api/v2/chat/sessions", headers=headers)
            assert r1.status_code == 200

            r2 = await client.get("/api/v2/chat/sessions", headers=headers)
            assert r2.status_code == 200

            # 2. 3rd request to /api/v2/chat/sessions is rate-limited (HTTP 429)
            r3 = await client.get("/api/v2/chat/sessions", headers=headers)
            assert r3.status_code == 429
            assert "Retry-After" in r3.headers
            assert "Rate limit exceeded" in r3.json()["detail"]

            # 3. Exempt path (/api/v2/health) still succeeds even after limit is exceeded
            r_health = await client.get("/api/v2/health", headers=headers)
            assert r_health.status_code == 200
            assert r_health.json()["status"] == "ok"

            # 4. Root path (/) is exempt as well
            r_root = await client.get("/", headers=headers)
            assert r_root.status_code == 200
    finally:
        # Restore limiter
        rate_limiter.reset()
        rate_limiter.set_enabled(orig_enabled)
        rate_limiter.set_limit(orig_limit)
