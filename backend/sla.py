from datetime import datetime, timedelta

# SLA window per priority, computed from created_at rather than persisted —
# the deadline is always derivable and shouldn't drift from whatever the
# priority happens to be at read time.
SLA_WINDOWS: dict[str, timedelta] = {
    "P0": timedelta(hours=2),
    "P1": timedelta(hours=12),
    "P2": timedelta(days=7),
    "P3": timedelta(days=14),
}


def sla_deadline(priority: str, created_at: datetime) -> datetime:
    return created_at + SLA_WINDOWS[priority]


def is_breached(priority: str, created_at: datetime, resolved_at: datetime | None, now: datetime) -> bool:
    """True if the SLA deadline passed before resolution (or before `now`,
    for a request that isn't resolved yet)."""
    deadline = sla_deadline(priority, created_at)
    reference_time = resolved_at if resolved_at is not None else now
    return reference_time > deadline
