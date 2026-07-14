from datetime import datetime, timezone


def utcnow() -> datetime:
    """Timezone-aware UTC now — matches the timezone-aware `DateTime` columns
    in models.py (Postgres `timestamptz`, read back as tz-aware by psycopg2),
    so this stays comparable to values read back from the DB. Replaces the
    deprecated `datetime.utcnow()`, which returns a naive value.
    """
    return datetime.now(timezone.utc)
