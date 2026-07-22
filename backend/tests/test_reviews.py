from unittest.mock import patch


def test_review_still_saves_if_email_fails(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])

    with patch("request_service.send_review_decision_email", side_effect=Exception("boom")):
        response = client.post(
            "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
        )

    assert response.status_code == 200
    assert response.json()["decision"] == "APPROVED"

    get_response = client.get(f"/requests/{request_id}/reviews", headers=auth_headers)
    assert len(get_response.json()) == 1


def test_get_reviews_admin_sees_all(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
    )

    admin = make_user(role="admin")
    response = client.get("/reviews", headers=admin["headers"])
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_reviews_reviewer_sees_only_own(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer_one = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer_one["headers"])
    client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "APPROVED"},
        headers=reviewer_one["headers"],
    )

    reviewer_two = make_user(role="reviewer")
    response = client.get("/reviews", headers=reviewer_two["headers"])
    assert response.status_code == 200
    assert response.json() == []


def test_get_reviews_requester_sees_empty_list(client, auth_headers):
    response = client.get("/reviews", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_get_request_reviews_not_found(client, make_user):
    admin = make_user(role="admin")
    response = client.get("/requests/9999/reviews", headers=admin["headers"])
    assert response.status_code == 404


def test_get_request_reviews_allowed_for_owner(client, auth_headers):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    response = client.get(f"/requests/{request_id}/reviews", headers=auth_headers)
    assert response.status_code == 200


def test_get_request_reviews_forbidden_for_unrelated_requester(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    other = make_user(role="requester")
    response = client.get(f"/requests/{request_id}/reviews", headers=other["headers"])
    assert response.status_code == 403


def test_get_request_reviews_allowed_for_admin(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
    )

    admin = make_user(role="admin")
    response = client.get(f"/requests/{request_id}/reviews", headers=admin["headers"])
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_request_reviews_allowed_for_claimant_reviewer(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])

    # Claimed but not yet reviewed — the claimant should still be able to see
    # (empty) review history for their own claim.
    response = client.get(f"/requests/{request_id}/reviews", headers=reviewer["headers"])
    assert response.status_code == 200
    assert response.json() == []


def test_get_request_reviews_allowed_for_reviewer_who_reviewed_it(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
    )

    # Even after an admin overrides the decision (claimed_by no longer
    # matters), the reviewer who actually wrote a review should still be
    # able to see it.
    admin = make_user(role="admin")
    client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "NOT APPROVED", "comment_text": "reversing"},
        headers=admin["headers"],
    )

    response = client.get(f"/requests/{request_id}/reviews", headers=reviewer["headers"])
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_request_reviews_forbidden_for_uninvolved_reviewer(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
    )

    other_reviewer = make_user(role="reviewer")
    response = client.get(f"/requests/{request_id}/reviews", headers=other_reviewer["headers"])
    assert response.status_code == 403
