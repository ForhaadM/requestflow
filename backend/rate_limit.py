import time
from collections import defaultdict, deque

from fastapi import HTTPException

# In-memory, single-process rate limiting: sufficient for this project's
# current deployment (one Uvicorn worker on one EC2 instance), but state is
# NOT shared across multiple workers/instances. A real multi-instance
# deployment needs a shared store (e.g. Redis) instead, or these limits are
# effectively "per-instance" rather than global.
_hits: dict[str, deque] = defaultdict(deque)


def enforce_rate_limit(key: str, *, max_requests: int, window_seconds: int) -> None:
    """Raise 429 if `key` has been hit more than `max_requests` times in the
    trailing `window_seconds`. Otherwise records this hit and returns."""
    now = time.monotonic()
    hits = _hits[key]
    while hits and now - hits[0] > window_seconds:
        hits.popleft()

    if len(hits) >= max_requests:
        raise HTTPException(
            status_code=429, detail="Too many requests. Please slow down and try again shortly."
        )

    hits.append(now)
