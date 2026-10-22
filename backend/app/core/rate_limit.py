import math
import time
from collections import defaultdict, deque

from app.core.errors import AppError


class SlidingWindowLimiter:
    """Simple in-memory limiter. Per-process only: with several workers each has its own counts."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] >= window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = max(1, math.ceil(window_seconds - (now - hits[0])))
            raise AppError(
                429,
                "rate_limited",
                "Too many attempts. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)
