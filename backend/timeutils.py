from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC now — matches the naive `DateTime` columns in models.py
    (Postgres `now()` is stored without a timezone), so this stays
    comparable to values read back from the DB. Replaces the deprecated
    `datetime.utcnow()`; a straight `datetime.now(timezone.utc)` would return
    a timezone-aware value that can't be compared against those columns.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
