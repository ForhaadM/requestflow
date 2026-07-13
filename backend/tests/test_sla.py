from datetime import timedelta

from sla import SLA_WINDOWS, is_breached, sla_deadline
from timeutils import utcnow


def test_sla_windows_cover_all_priorities():
    assert SLA_WINDOWS["P0"] == timedelta(hours=2)
    assert SLA_WINDOWS["P1"] == timedelta(hours=12)
    assert SLA_WINDOWS["P2"] == timedelta(days=7)
    assert SLA_WINDOWS["P3"] == timedelta(days=14)


def test_sla_deadline_is_created_at_plus_window():
    created_at = utcnow()
    assert sla_deadline("P0", created_at) == created_at + timedelta(hours=2)


def test_is_breached_true_when_resolved_after_deadline():
    created_at = utcnow() - timedelta(hours=3)
    resolved_at = utcnow()
    assert is_breached("P0", created_at, resolved_at, utcnow()) is True


def test_is_breached_false_when_resolved_within_window():
    created_at = utcnow() - timedelta(hours=1)
    resolved_at = utcnow()
    assert is_breached("P0", created_at, resolved_at, utcnow()) is False


def test_is_breached_uses_now_when_not_yet_resolved():
    created_at = utcnow() - timedelta(days=1)
    assert is_breached("P0", created_at, None, utcnow()) is True
    assert is_breached("P3", created_at, None, utcnow()) is False
