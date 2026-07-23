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
    body = response.json()
    assert len(body["items"]) == 1
    assert body["total"] == 1
    assert body["items"][0]["request"]["request_id"] == request_id


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
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_get_reviews_requester_sees_empty_list(client, auth_headers):
    response = client.get("/reviews", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


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


# --- GET /reviews pagination -------------------------------------------------


def _make_reviewed_request(
    client, requester_headers, reviewer_headers, request_type="hardware", priority="P1", decision="APPROVED"
):
    create_response = client.post(
        "/requests",
        json={"request_type": request_type, "description": f"{request_type} request", "priority": priority},
        headers=requester_headers,
    )
    request_id = create_response.json()["request_id"]
    client.patch(f"/requests/{request_id}/claim", headers=reviewer_headers)

    payload = {"request_reference": request_id, "decision": decision}
    if decision == "NOT APPROVED":
        payload["comment_text"] = "rejecting"
    review_response = client.post("/reviews", json=payload, headers=reviewer_headers)
    assert review_response.status_code == 200
    return request_id, review_response.json()


def test_reviews_pagination_slices_the_filtered_set(client, auth_headers, make_user):
    admin = make_user(role="admin")
    request_ids = []
    for _ in range(5):
        request_id, _ = _make_reviewed_request(client, auth_headers, admin["headers"])
        request_ids.append(request_id)

    page1 = client.get("/reviews?page=1&page_size=2", headers=admin["headers"]).json()
    page2 = client.get("/reviews?page=2&page_size=2", headers=admin["headers"]).json()
    page3 = client.get("/reviews?page=3&page_size=2", headers=admin["headers"]).json()

    assert page1["total"] == page2["total"] == page3["total"] == 5
    assert page1["total_pages"] == page2["total_pages"] == page3["total_pages"] == 3
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2
    assert len(page3["items"]) == 1

    # Newest-first by default, and no review should appear on two pages.
    all_request_ids = [rv["request_reference"] for rv in page1["items"] + page2["items"] + page3["items"]]
    assert all_request_ids == sorted(request_ids, reverse=True)


def test_reviews_out_of_range_page_returns_empty_items(client, auth_headers, make_user):
    admin = make_user(role="admin")
    _make_reviewed_request(client, auth_headers, admin["headers"])

    response = client.get("/reviews?page=999&page_size=10", headers=admin["headers"])
    body = response.json()
    assert response.status_code == 200
    assert body["items"] == []
    assert body["total"] == 1
    assert body["page"] == 999


def test_reviews_page_size_capped_at_100(client, make_user):
    admin = make_user(role="admin")

    response = client.get("/reviews?page_size=101", headers=admin["headers"])
    assert response.status_code == 422

    response = client.get("/reviews?page_size=100", headers=admin["headers"])
    assert response.status_code == 200
    assert response.json()["page_size"] == 100


def test_reviews_search_composes_with_pagination(client, make_user):
    admin = make_user(role="admin")
    rita = make_user(role="requester")
    client.post(
        "/users",
        json={"name": "Rita Printer", "email": "rita.printer2@example.com", "password": "Password123!", "role": "requester"},
    )
    rita_login = client.post("/login", json={"email": "rita.printer2@example.com", "password": "Password123!"})
    rita_headers = {"Authorization": f"Bearer {rita_login.json()['access_token']}"}

    rita_request_id, _ = _make_reviewed_request(client, rita_headers, admin["headers"])
    _make_reviewed_request(client, admin["headers"], admin["headers"])

    response = client.get("/reviews?search=Printer&page_size=10", headers=admin["headers"])
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["request_reference"] == rita_request_id


def test_reviews_priority_and_type_filters_compose_with_pagination(client, auth_headers, make_user):
    admin = make_user(role="admin")
    hardware_id, _ = _make_reviewed_request(client, auth_headers, admin["headers"], request_type="hardware", priority="P1")
    software_id, _ = _make_reviewed_request(client, auth_headers, admin["headers"], request_type="software", priority="P2")

    by_type = client.get("/reviews?request_type=software", headers=admin["headers"]).json()
    assert by_type["total"] == 1
    assert by_type["items"][0]["request_reference"] == software_id

    by_priority = client.get("/reviews?priority=P1", headers=admin["headers"]).json()
    assert by_priority["total"] == 1
    assert by_priority["items"][0]["request_reference"] == hardware_id


def test_reviews_decision_filter_composes_with_pagination(client, auth_headers, make_user):
    admin = make_user(role="admin")
    approved_id, _ = _make_reviewed_request(client, auth_headers, admin["headers"], decision="APPROVED")
    rejected_id, _ = _make_reviewed_request(client, auth_headers, admin["headers"], decision="NOT APPROVED")

    approved = client.get("/reviews?decision=APPROVED", headers=admin["headers"]).json()
    assert approved["total"] == 1
    assert approved["items"][0]["request_reference"] == approved_id

    rejected = client.get("/reviews?decision=NOT APPROVED", headers=admin["headers"]).json()
    assert rejected["total"] == 1
    assert rejected["items"][0]["request_reference"] == rejected_id


def test_reviews_reviewer_scoping_composes_with_pagination(client, auth_headers, make_user):
    reviewer_one = make_user(role="reviewer")
    reviewer_two = make_user(role="reviewer")
    _make_reviewed_request(client, auth_headers, reviewer_one["headers"])
    _make_reviewed_request(client, auth_headers, reviewer_one["headers"])
    _make_reviewed_request(client, auth_headers, reviewer_two["headers"])

    response = client.get("/reviews?page_size=10", headers=reviewer_one["headers"])
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert all(rv["reviewer_reference"] == reviewer_one["user_id"] for rv in body["items"])


def test_reviews_items_include_nested_request_detail(client, auth_headers, make_user):
    admin = make_user(role="admin")
    request_id, _ = _make_reviewed_request(client, auth_headers, admin["headers"], request_type="hardware", priority="P2")

    response = client.get("/reviews", headers=admin["headers"])
    item = response.json()["items"][0]
    assert item["request"]["request_id"] == request_id
    assert item["request"]["request_type"] == "hardware"
    assert item["request"]["priority"] == "P2"
