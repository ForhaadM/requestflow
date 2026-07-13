from datetime import datetime, timedelta

from models import Requests, Reviews
from timeutils import utcnow
import analytics


def _backdate_request(db_session, request_id: int, created_at: datetime):
    db_session.query(Requests).filter(Requests.request_id == request_id).update({"created_at": created_at})
    db_session.commit()


def _backdate_review(db_session, review_id: int, reviewed_at: datetime):
    db_session.query(Reviews).filter(Reviews.review_id == review_id).update({"reviewed_at": reviewed_at})
    db_session.commit()


def _create_request(client, headers, request_type="hardware", description="desc", priority="P1"):
    payload = {"request_type": request_type, "description": description, "priority": priority}
    if priority == "P0":
        payload["urgency_justification"] = "very urgent"
    response = client.post("/requests", json=payload, headers=headers)
    assert response.status_code == 200
    return response.json()["request_id"]


def test_admin_analytics_requires_admin(client, auth_headers):
    response = client.get("/admin/analytics", headers=auth_headers)
    assert response.status_code == 403


def test_admin_analytics_allowed_for_admin_and_has_expected_shape(client, make_user):
    admin = make_user(role="admin")
    response = client.get("/admin/analytics", headers=admin["headers"])
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "volume_by_category",
        "spikes",
        "avg_resolution_by_category",
        "avg_resolution_by_priority",
        "sla_compliance",
    }
    # every request_type should be represented even with zero data
    assert len(body["volume_by_category"]) == 9
    assert len(body["avg_resolution_by_category"]) == 9
    assert len(body["avg_resolution_by_priority"]) == 4


def test_volume_trend_up_when_recent_exceeds_previous(client, auth_headers, db_session):
    now = utcnow()
    # one request in the "previous" half of the 30-day window
    old_id = _create_request(client, auth_headers, request_type="software", description="old one")
    _backdate_request(db_session, old_id, now - timedelta(days=20))

    # two requests in the "recent" half
    for i in range(2):
        rid = _create_request(client, auth_headers, request_type="software", description=f"recent {i}")
        _backdate_request(db_session, rid, now - timedelta(days=5))

    results = {r["request_type"]: r for r in analytics.get_volume_trends(db_session, now=now)}
    software = results["software"]
    assert software["previous_15d"] == 1
    assert software["recent_15d"] == 2
    assert software["trend"] == "up"


def test_volume_trend_down_when_recent_below_previous(client, auth_headers, db_session):
    now = utcnow()
    for i in range(3):
        rid = _create_request(client, auth_headers, request_type="network", description=f"old {i}")
        _backdate_request(db_session, rid, now - timedelta(days=20))

    rid = _create_request(client, auth_headers, request_type="network", description="recent")
    _backdate_request(db_session, rid, now - timedelta(days=5))

    results = {r["request_type"]: r for r in analytics.get_volume_trends(db_session, now=now)}
    assert results["network"]["trend"] == "down"


def test_volume_trend_excludes_requests_outside_30_day_window(client, auth_headers, db_session):
    now = utcnow()
    old_id = _create_request(client, auth_headers, request_type="facilities", description="ancient")
    _backdate_request(db_session, old_id, now - timedelta(days=40))

    results = {r["request_type"]: r for r in analytics.get_volume_trends(db_session, now=now)}
    assert results["facilities"]["total_30d"] == 0


def test_spike_detected_when_recent_volume_far_exceeds_baseline(client, auth_headers, db_session):
    now = utcnow()
    # light, steady baseline over the trailing 4 weeks (well before the last 7 days)
    for i in range(2):
        rid = _create_request(client, auth_headers, request_type="bug-report", description=f"baseline {i}")
        _backdate_request(db_session, rid, now - timedelta(days=14 + i))

    # sudden burst in the last 7 days
    for i in range(6):
        rid = _create_request(client, auth_headers, request_type="bug-report", description=f"burst {i}")
        _backdate_request(db_session, rid, now - timedelta(days=1))

    spikes = {s["request_type"]: s for s in analytics.get_spikes(db_session, now=now)}
    assert "bug-report" in spikes
    assert spikes["bug-report"]["recent_count"] == 6


def test_spike_not_flagged_for_low_volume_category(client, auth_headers, db_session):
    now = utcnow()
    rid = _create_request(client, auth_headers, request_type="other", description="single request")
    _backdate_request(db_session, rid, now - timedelta(days=1))

    spikes = {s["request_type"] for s in analytics.get_spikes(db_session, now=now)}
    # below SPIKE_MIN_COUNT, so it should never be flagged regardless of baseline
    assert "other" not in spikes


def test_avg_resolution_by_category_computes_days_between_creation_and_first_decision(
    client, auth_headers, make_user, db_session
):
    request_id = _create_request(client, auth_headers, request_type="access-request", description="need access")
    _backdate_request(db_session, request_id, utcnow() - timedelta(days=5))

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    review_response = client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "APPROVED", "comment_text": "granted"},
        headers=reviewer["headers"],
    )
    review_id = review_response.json()["review_id"]
    _backdate_review(db_session, review_id, utcnow() - timedelta(days=2))

    results = {r["request_type"]: r for r in analytics.get_avg_resolution_by_category(db_session)}
    assert results["access-request"]["resolved_count"] == 1
    # created 5 days ago, decided 2 days ago -> ~3 days to resolve
    assert 2.9 <= results["access-request"]["avg_days"] <= 3.1


def test_avg_resolution_ignores_unresolved_requests(client, auth_headers, db_session):
    _create_request(client, auth_headers, request_type="onboarding-offboarding", description="still open")

    results = {r["request_type"]: r for r in analytics.get_avg_resolution_by_category(db_session)}
    assert results["onboarding-offboarding"]["resolved_count"] == 0
    assert results["onboarding-offboarding"]["avg_days"] == 0


def test_avg_resolution_by_priority_reports_all_priorities(client, auth_headers, db_session):
    results = {r["priority"]: r for r in analytics.get_avg_resolution_by_priority(db_session)}
    assert set(results.keys()) == {"P0", "P1", "P2", "P3"}


def test_sla_compliance_counts_resolved_request_decided_within_window_as_met(
    client, auth_headers, make_user, db_session
):
    # P2 SLA is 7 days; created 5 days ago and decided 1 day ago -> well within the window.
    request_id = _create_request(client, auth_headers, priority="P2", description="within sla")
    _backdate_request(db_session, request_id, utcnow() - timedelta(days=5))

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    review_response = client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "APPROVED", "comment_text": "done"},
        headers=reviewer["headers"],
    )
    _backdate_review(db_session, review_response.json()["review_id"], utcnow() - timedelta(days=1))

    results = {r["priority"]: r for r in analytics.get_sla_compliance(db_session)["by_priority"]}
    assert results["P2"]["resolved_met"] == 1
    assert results["P2"]["resolved_breached"] == 0


def test_sla_compliance_counts_resolved_request_decided_after_window_as_breached(
    client, auth_headers, make_user, db_session
):
    # P1 SLA is 12 hours; created 3 days ago and decided just now -> breached.
    request_id = _create_request(client, auth_headers, priority="P1", description="breached sla")
    _backdate_request(db_session, request_id, utcnow() - timedelta(days=3))

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "APPROVED", "comment_text": "done"},
        headers=reviewer["headers"],
    )

    results = {r["priority"]: r for r in analytics.get_sla_compliance(db_session)["by_priority"]}
    assert results["P1"]["resolved_breached"] == 1
    assert results["P1"]["resolved_met"] == 0


def test_sla_compliance_flags_still_open_request_past_deadline(client, auth_headers, db_session):
    # P0 SLA is 2 hours; created 1 day ago and still open -> currently breached.
    request_id = _create_request(client, auth_headers, priority="P0", description="urgent still open")
    _backdate_request(db_session, request_id, utcnow() - timedelta(days=1))

    results = {r["priority"]: r for r in analytics.get_sla_compliance(db_session)["by_priority"]}
    assert results["P0"]["currently_breached_open"] == 1


def test_sla_compliance_reports_all_priorities_with_null_rate_when_no_data(client, db_session):
    results = {r["priority"]: r for r in analytics.get_sla_compliance(db_session)["by_priority"]}
    assert set(results.keys()) == {"P0", "P1", "P2", "P3"}
    assert results["P0"]["compliance_rate"] is None
