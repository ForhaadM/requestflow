from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Requests, Reviews, REQUEST_TYPES, PRIORITIES

# Pure SQL aggregation over existing requests/reviews data — no AI/LLM calls,
# no schema changes. Thresholds below are deliberately simple ("directionally
# useful", not statistically rigorous) per the brief.

WINDOW_DAYS = 30
RECENT_DAYS = 15  # 30-day window is split into two 15-day halves for trend direction

SPIKE_WINDOW_DAYS = 7
SPIKE_BASELINE_WEEKS = 4
SPIKE_THRESHOLD = 1.5  # recent 7-day count must be >= 1.5x the expected (baseline-derived) count
SPIKE_MIN_COUNT = 3  # ignore near-zero categories — avoids flagging e.g. "1 request instead of 0"

TERMINAL_STATUSES = ("approved", "rejected")


def _volume_by_category(db: Session, since: datetime, until: datetime) -> dict[str, int]:
    rows = (
        db.query(Requests.request_type, func.count(Requests.request_id))
        .filter(Requests.created_at >= since, Requests.created_at < until)
        .group_by(Requests.request_type)
        .all()
    )
    return {request_type: count for request_type, count in rows}


def get_volume_trends(db: Session, now: datetime | None = None) -> list[dict]:
    """Request volume by category over the last 30 days, split into two 15-day
    halves so we can say whether each category is trending up or down."""
    now = now or datetime.utcnow()
    window_start = now - timedelta(days=WINDOW_DAYS)
    midpoint = now - timedelta(days=RECENT_DAYS)

    previous_counts = _volume_by_category(db, window_start, midpoint)
    recent_counts = _volume_by_category(db, midpoint, now)

    results = []
    for request_type in REQUEST_TYPES:
        recent = recent_counts.get(request_type, 0)
        previous = previous_counts.get(request_type, 0)
        if recent == previous:
            trend = "flat"
        elif previous == 0 or recent > previous:
            trend = "up"
        else:
            trend = "down"
        results.append(
            {
                "request_type": request_type,
                "total_30d": recent + previous,
                "recent_15d": recent,
                "previous_15d": previous,
                "trend": trend,
            }
        )
    return results


def get_spikes(db: Session, now: datetime | None = None) -> list[dict]:
    """Categories whose volume in the last 7 days is well above what their
    trailing 4-week average would predict for a 7-day window."""
    now = now or datetime.utcnow()
    baseline_days = SPIKE_BASELINE_WEEKS * 7
    baseline_start = now - timedelta(days=baseline_days + SPIKE_WINDOW_DAYS)
    baseline_end = now - timedelta(days=SPIKE_WINDOW_DAYS)
    recent_start = now - timedelta(days=SPIKE_WINDOW_DAYS)

    baseline_counts = _volume_by_category(db, baseline_start, baseline_end)
    recent_counts = _volume_by_category(db, recent_start, now)

    spikes = []
    for request_type in REQUEST_TYPES:
        recent = recent_counts.get(request_type, 0)
        if recent < SPIKE_MIN_COUNT:
            continue

        baseline_total = baseline_counts.get(request_type, 0)
        baseline_daily_avg = baseline_total / baseline_days
        expected = baseline_daily_avg * SPIKE_WINDOW_DAYS

        is_spike = recent >= SPIKE_MIN_COUNT if expected == 0 else recent >= expected * SPIKE_THRESHOLD
        if is_spike:
            spikes.append(
                {
                    "request_type": request_type,
                    "recent_count": recent,
                    "expected_count": round(expected, 1),
                }
            )
    return spikes


def _first_decision_subquery(db: Session):
    """One row per request that has at least one review: the timestamp of its
    earliest (first) decision — used as "when it was resolved"."""
    return (
        db.query(
            Reviews.request_reference.label("request_id"),
            func.min(Reviews.reviewed_at).label("first_reviewed_at"),
        )
        .group_by(Reviews.request_reference)
        .subquery()
    )


def _avg_resolution_by(db: Session, group_column) -> list[dict]:
    first_review = _first_decision_subquery(db)
    avg_seconds_expr = func.avg(
        func.extract("epoch", first_review.c.first_reviewed_at - Requests.created_at)
    )
    rows = (
        db.query(group_column, avg_seconds_expr, func.count(Requests.request_id))
        .join(first_review, first_review.c.request_id == Requests.request_id)
        .filter(Requests.status.in_(TERMINAL_STATUSES))
        .group_by(group_column)
        .all()
    )
    return [
        {
            "key": key,
            "avg_days": round((avg_seconds or 0) / 86400, 1),
            "resolved_count": count,
        }
        for key, avg_seconds, count in rows
    ]


def get_avg_resolution_by_category(db: Session) -> list[dict]:
    rows = {row["key"]: row for row in _avg_resolution_by(db, Requests.request_type)}
    # Report all categories (even with 0 resolved) so the chart doesn't
    # silently drop a category that just hasn't had a decision yet.
    return [
        {
            "request_type": request_type,
            "avg_days": rows[request_type]["avg_days"] if request_type in rows else 0,
            "resolved_count": rows[request_type]["resolved_count"] if request_type in rows else 0,
        }
        for request_type in REQUEST_TYPES
    ]


def get_avg_resolution_by_priority(db: Session) -> list[dict]:
    rows = {row["key"]: row for row in _avg_resolution_by(db, Requests.priority)}
    # Report all four priorities (even with 0 resolved) so the chart doesn't
    # silently drop a priority that just hasn't had a decision yet.
    return [
        {
            "priority": p,
            "avg_days": rows[p]["avg_days"] if p in rows else 0,
            "resolved_count": rows[p]["resolved_count"] if p in rows else 0,
        }
        for p in PRIORITIES
    ]


def get_admin_analytics(db: Session) -> dict:
    return {
        "volume_by_category": get_volume_trends(db),
        "spikes": get_spikes(db),
        "avg_resolution_by_category": get_avg_resolution_by_category(db),
        "avg_resolution_by_priority": get_avg_resolution_by_priority(db),
    }
