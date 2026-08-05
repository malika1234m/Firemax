import time
import uuid
import logging
from collections import defaultdict
from fastapi import HTTPException, Request

from app.config import settings

logger = logging.getLogger(__name__)

# ── Client IP resolution ─────────────────────────────────────────────────────
# Behind a load balancer, request.client.host is the LB's IP, so every user
# shares one bucket. We instead read the real client from X-Forwarded-For — but
# only as far back as TRUSTED_PROXY_COUNT hops, because XFF is client-spoofable
# for any hop beyond the proxies we actually control.


def client_ip(request: Request) -> str:
    proxies = settings.TRUSTED_PROXY_COUNT
    if proxies > 0:
        xff = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        # Each trusted proxy appends the peer it saw, so the real client is the
        # Nth entry from the RIGHT (N = trusted-proxy depth). Counting from the
        # right is what makes this spoof-resistant: a client can prepend fake
        # left-hand entries, but it can't push past the values our own proxies
        # appended. If the header is shorter than the configured depth it's
        # missing/misconfigured, so we distrust it and use the socket peer.
        if len(parts) >= proxies:
            return parts[len(parts) - proxies]
    return request.client.host if request.client else "unknown"


# ── Sliding-window stores ────────────────────────────────────────────────────
# Both return (allowed: bool, retry_after_seconds: int).

# Process-local fallback for single-instance / local dev. Kept module-level and
# named `_attempts` because the test suite clears it between cases.
_attempts: dict[str, list[float]] = defaultdict(list)


def _memory_hit(key: str, max_attempts: int, window_seconds: int) -> tuple[bool, int]:
    now = time.time()
    window_start = now - window_seconds
    attempts = _attempts[key]
    while attempts and attempts[0] < window_start:
        attempts.pop(0)
    if len(attempts) >= max_attempts:
        retry_after = int(window_seconds - (now - attempts[0])) + 1
        return False, retry_after
    attempts.append(now)
    return True, 0


# Redis-backed shared window (required once more than one instance runs). Lazily
# connected; if REDIS_URL is unreachable we fail OPEN and log, so a Redis blip
# degrades protection rather than locking every user out of auth.
_redis = None
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local maxn = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= maxn then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  return {1, oldest[2]}
end
redis.call('ZADD', key, now, member)
redis.call('PEXPIRE', key, math.floor(window * 1000))
return {0, '0'}
"""


def _get_redis():
    global _redis
    if _redis is None:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
    return _redis


async def _redis_hit(key: str, max_attempts: int, window_seconds: int) -> tuple[bool, int]:
    now = time.time()
    try:
        r = _get_redis()
        limited, oldest = await r.eval(
            _SLIDING_WINDOW_LUA, 1, key,
            str(now), str(window_seconds), str(max_attempts), f"{now}-{uuid.uuid4().hex}",
        )
        if int(limited) == 1:
            retry_after = int(window_seconds - (now - float(oldest))) + 1
            return False, max(retry_after, 1)
        return True, 0
    except Exception:
        logger.exception("[rate_limit] Redis unavailable — failing open for this request")
        return True, 0


def rate_limiter(max_attempts: int, window_seconds: int):
    """FastAPI dependency: allow at most `max_attempts` calls to this route per
    `window_seconds` from a given client IP."""

    async def _check(request: Request):
        key = f"ratelimit:{request.url.path}:{client_ip(request)}"
        if settings.REDIS_URL:
            allowed, retry_after = await _redis_hit(key, max_attempts, window_seconds)
        else:
            allowed, retry_after = _memory_hit(key, max_attempts, window_seconds)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many attempts. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    return _check
