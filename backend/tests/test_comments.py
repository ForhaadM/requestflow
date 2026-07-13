def _create_request(client, headers, description="Test request"):
    response = client.post("/requests", json={"request_type": "hardware", "description": description}, headers=headers)
    assert response.status_code == 200
    return response.json()["request_id"]


def test_owner_can_add_and_list_comment(client, auth_headers):
    request_id = _create_request(client, auth_headers)

    add_response = client.post(
        f"/requests/{request_id}/comments", json={"comment_text": "Forgot to mention: it's urgent."}, headers=auth_headers
    )
    assert add_response.status_code == 200
    body = add_response.json()
    assert body["comment_text"] == "Forgot to mention: it's urgent."
    assert body["request_reference"] == request_id

    list_response = client.get(f"/requests/{request_id}/comments", headers=auth_headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_non_owner_requester_cannot_add_comment(client, auth_headers, make_user):
    request_id = _create_request(client, auth_headers)
    other = make_user(role="requester")

    response = client.post(
        f"/requests/{request_id}/comments", json={"comment_text": "Not my request"}, headers=other["headers"]
    )
    assert response.status_code == 403


def test_non_owner_requester_cannot_list_comments(client, auth_headers, make_user):
    request_id = _create_request(client, auth_headers)
    other = make_user(role="requester")

    response = client.get(f"/requests/{request_id}/comments", headers=other["headers"])
    assert response.status_code == 403


def test_reviewer_can_list_but_not_add_comments(client, auth_headers, make_user):
    request_id = _create_request(client, auth_headers)
    reviewer = make_user(role="reviewer")

    list_response = client.get(f"/requests/{request_id}/comments", headers=reviewer["headers"])
    assert list_response.status_code == 200

    add_response = client.post(
        f"/requests/{request_id}/comments", json={"comment_text": "Reviewer trying to comment"}, headers=reviewer["headers"]
    )
    assert add_response.status_code == 403


def test_admin_can_list_comments(client, auth_headers, make_user):
    request_id = _create_request(client, auth_headers)
    client.post(f"/requests/{request_id}/comments", json={"comment_text": "context"}, headers=auth_headers)

    admin = make_user(role="admin")
    response = client.get(f"/requests/{request_id}/comments", headers=admin["headers"])
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_comment_over_max_length_rejected(client, auth_headers):
    request_id = _create_request(client, auth_headers)
    response = client.post(
        f"/requests/{request_id}/comments", json={"comment_text": "x" * 751}, headers=auth_headers
    )
    assert response.status_code == 422


def test_empty_comment_rejected(client, auth_headers):
    request_id = _create_request(client, auth_headers)
    response = client.post(f"/requests/{request_id}/comments", json={"comment_text": ""}, headers=auth_headers)
    assert response.status_code == 422


def test_comment_on_nonexistent_request_not_found(client, auth_headers):
    response = client.post("/requests/9999/comments", json={"comment_text": "hi"}, headers=auth_headers)
    assert response.status_code == 404


def test_comments_returned_in_chronological_order(client, auth_headers):
    request_id = _create_request(client, auth_headers)
    client.post(f"/requests/{request_id}/comments", json={"comment_text": "first"}, headers=auth_headers)
    client.post(f"/requests/{request_id}/comments", json={"comment_text": "second"}, headers=auth_headers)

    response = client.get(f"/requests/{request_id}/comments", headers=auth_headers)
    texts = [c["comment_text"] for c in response.json()]
    assert texts == ["first", "second"]
