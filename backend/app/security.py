"""Rate limiting and HTTP security headers."""
import hashlib
import threading
import time

from fastapi import HTTPException, Request

from .config import settings

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
       "media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; "
       "frame-ancestors 'none'; form-action 'self'")

SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """Fixed one-minute window per (API key, IP). Redis when available (shared by all processes),
    otherwise an in-process counter (thread mode without Redis)."""

    def __init__(self, per_min: int):
        self.per_min = per_min
        self._local: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()
        self._redis = None
        if settings.queue_mode == "rq":
            from redis import Redis

            self._redis = Redis.from_url(settings.redis_url, socket_timeout=2)

    def hit(self, key: str, ip: str) -> bool:
        if self.per_min <= 0:
            return True
        window = int(time.time() // 60)
        ident = hashlib.sha256(f"{key}|{ip}".encode()).hexdigest()[:32]  # never store the key itself
        name = f"rl:analyze:{ident}:{window}"
        if self._redis is not None:
            try:
                pipe = self._redis.pipeline()
                pipe.incr(name)
                pipe.expire(name, 120)
                count = pipe.execute()[0]
                return count <= self.per_min
            except Exception:
                pass  # Redis hiccup: fall back to the local counter rather than reject the jury
        with self._lock:
            w, c = self._local.get(ident, (window, 0))
            c = c + 1 if w == window else 1
            self._local[ident] = (window, c)
            return c <= self.per_min


limiter = RateLimiter(settings.rate_limit_per_min)


def check_rate(request: Request, key: str):
    if not limiter.hit(key, client_ip(request)):
        raise HTTPException(429, "Too many requests, try again in a minute", headers={"Retry-After": "60"})
