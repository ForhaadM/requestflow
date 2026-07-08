def test_create_request_no_token_rejected(client):
    response = client.post(
        "/requests",
        json={"request_type": "hardware", "description": "New laptop"},
    )
    assert response.status_code == 401


def test_create_request_requester_reference_from_token(client, registered_user, auth_headers):
    response = client.post(
        "/requests",
        json={"request_type": "hardware", "description": "New laptop"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requester_reference"] == registered_user["user_id"]


def test_create_review_reviewer_reference_from_token(client, registered_user, auth_headers, make_user):
    request_response = client.post(
        "/requests",
        json={"request_type": "hardware", "description": "New laptop"},
        headers=auth_headers,
    )
    request_id = request_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    review_response = client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "APPROVED"},
        headers=reviewer["headers"],
    )
    assert review_response.status_code == 200
    body = review_response.json()
    assert body["reviewer_reference"] == reviewer["user_id"]
    assert body["reviewer_reference"] != registered_user["user_id"]


def test_create_review_forbidden_for_requester(client, auth_headers):
    request_response = client.post(
        "/requests",
        json={"request_type": "hardware", "description": "New laptop"},
        headers=auth_headers,
    )
    request_id = request_response.json()["request_id"]

    response = client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "APPROVED"},
        headers=auth_headers,
    )
    assert response.status_code == 403


def test_create_review_request_not_found(client, make_user):
    reviewer = make_user(role="reviewer")
    response = client.post(
        "/reviews",
        json={"request_reference": 9999, "decision": "APPROVED"},
        headers=reviewer["headers"],
    )
    assert response.status_code == 404


def test_create_review_rejection_without_comment_fails(client, auth_headers, make_user):
    request_response = client.post(
        "/requests",
        json={"request_type": "hardware", "description": "New laptop"},
        headers=auth_headers,
    )
    request_id = request_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    review_response = client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "NOT APPROVED"},
        headers=reviewer["headers"],
    )
    assert review_response.status_code == 400
