def test_create_request_without_description_fails(client, auth_headers):
    response = client.post("/requests", json={"request_type": "hardware"}, headers=auth_headers)
    assert response.status_code == 400


def test_create_request_with_blank_description_fails(client, auth_headers):
    response = client.post(
        "/requests", json={"request_type": "hardware", "description": "   "}, headers=auth_headers
    )
    assert response.status_code == 400


def test_get_all_requests_forbidden_for_non_admin(client, auth_headers):
    response = client.get("/requests", headers=auth_headers)
    assert response.status_code == 403


def test_get_all_requests_allowed_for_admin(client, auth_headers, make_user):
    client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)

    admin = make_user(role="admin")
    response = client.get("/requests", headers=admin["headers"])
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_my_requests_returns_only_own(client, auth_headers, make_user):
    client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)

    other = make_user(role="requester")
    client.post("/requests", json={"request_type": "software", "description": "Test request"}, headers=other["headers"])

    response = client.get("/requests/me", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["request_type"] == "hardware"


def test_get_request_by_id_not_found(client, auth_headers):
    response = client.get("/requests/9999", headers=auth_headers)
    assert response.status_code == 404


def test_get_request_by_id_owner_can_view(client, auth_headers):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    response = client.get(f"/requests/{request_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["request_id"] == request_id


def test_get_request_by_id_forbidden_for_other_user(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    other = make_user(role="requester")
    response = client.get(f"/requests/{request_id}", headers=other["headers"])
    assert response.status_code == 403


def test_get_request_by_id_admin_can_view_any(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    admin = make_user(role="admin")
    response = client.get(f"/requests/{request_id}", headers=admin["headers"])
    assert response.status_code == 200


def test_patch_status_forbidden_for_requester(client, auth_headers):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    response = client.patch(f"/requests/{request_id}/status", json={"status": "closed"}, headers=auth_headers)
    assert response.status_code == 403


def test_patch_status_not_found(client, make_user):
    reviewer = make_user(role="reviewer")
    response = client.patch("/requests/9999/status", json={"status": "closed"}, headers=reviewer["headers"])
    assert response.status_code == 404


def test_patch_status_success_for_reviewer(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    response = client.patch(
        f"/requests/{request_id}/status", json={"status": "closed"}, headers=reviewer["headers"]
    )
    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_patch_status_forbidden_once_decided(client, auth_headers, make_user):
    # PATCH /requests/{id}/status must not be usable to silently reopen a
    # decided request — that would bypass POST /reviews' admin-only,
    # comment-required override protection entirely.
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
    )

    response = client.patch(
        f"/requests/{request_id}/status", json={"status": "open"}, headers=reviewer["headers"]
    )
    assert response.status_code == 400

    check = client.get(f"/requests/{request_id}", headers=auth_headers)
    assert check.json()["status"] == "approved"
