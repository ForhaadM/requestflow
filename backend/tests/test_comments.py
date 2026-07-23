from sqlalchemy import event


def _count_queries(engine, fn):
    """Runs `fn` and returns how many SQL statements it issued — used to prove
    list_comments_for_request's commenter-name lookup is a single batched
    query regardless of how many distinct commenters there are, not one
    query per commenter (N+1)."""
    count = 0

    def before_cursor_execute(*args, **kwargs):
        nonlocal count
        count += 1

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
    return count


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


def test_reviewer_can_list_but_not_add_comments_when_unclaimed(client, auth_headers, make_user):
    request_id = _create_request(client, auth_headers)
    reviewer = make_user(role="reviewer")

    list_response = client.get(f"/requests/{request_id}/comments", headers=reviewer["headers"])
    assert list_response.status_code == 200

    add_response = client.post(
        f"/requests/{request_id}/comments", json={"comment_text": "Reviewer trying to comment"}, headers=reviewer["headers"]
    )
    assert add_response.status_code == 403


def test_claimed_reviewer_can_add_comment(client, auth_headers, make_user):
    request_id = _create_request(client, auth_headers)
    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])

    response = client.post(
        f"/requests/{request_id}/comments", json={"comment_text": "Working on this now"}, headers=reviewer["headers"]
    )
    assert response.status_code == 200
    assert response.json()["comment_text"] == "Working on this now"


def test_non_claiming_reviewer_cannot_add_comment_on_claimed_ticket(client, auth_headers, make_user):
    request_id = _create_request(client, auth_headers)
    claimant = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=claimant["headers"])

    other_reviewer = make_user(role="reviewer")
    response = client.post(
        f"/requests/{request_id}/comments", json={"comment_text": "Not my ticket"}, headers=other_reviewer["headers"]
    )
    assert response.status_code == 403


def test_reviewer_loses_comment_access_after_unclaiming(client, auth_headers, make_user):
    request_id = _create_request(client, auth_headers)
    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.patch(f"/requests/{request_id}/unclaim", headers=reviewer["headers"])

    response = client.post(
        f"/requests/{request_id}/comments", json={"comment_text": "Still trying"}, headers=reviewer["headers"]
    )
    assert response.status_code == 403


def test_admin_can_add_comment_without_claiming(client, auth_headers, make_user):
    request_id = _create_request(client, auth_headers)
    admin = make_user(role="admin")

    response = client.post(
        f"/requests/{request_id}/comments", json={"comment_text": "Admin note"}, headers=admin["headers"]
    )
    assert response.status_code == 200


def test_admin_can_list_comments(client, auth_headers, make_user):
    request_id = _create_request(client, auth_headers)
    client.post(f"/requests/{request_id}/comments", json={"comment_text": "context"}, headers=auth_headers)

    admin = make_user(role="admin")
    response = client.get(f"/requests/{request_id}/comments", headers=admin["headers"])
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_claimed_reviewer_can_comment_after_request_approved(client, auth_headers, make_user):
    request_id = _create_request(client, auth_headers)
    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
    )

    response = client.post(
        f"/requests/{request_id}/comments", json={"comment_text": "Following up after approval"}, headers=reviewer["headers"]
    )
    assert response.status_code == 200


def test_admin_can_comment_after_request_rejected(client, auth_headers, make_user):
    request_id = _create_request(client, auth_headers)
    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "NOT APPROVED", "comment_text": "Not needed"},
        headers=reviewer["headers"],
    )

    admin = make_user(role="admin")
    response = client.post(
        f"/requests/{request_id}/comments", json={"comment_text": "Admin follow-up"}, headers=admin["headers"]
    )
    assert response.status_code == 200


def test_owner_can_comment_after_request_approved(client, auth_headers, make_user):
    request_id = _create_request(client, auth_headers)
    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
    )

    response = client.post(
        f"/requests/{request_id}/comments", json={"comment_text": "Thanks!"}, headers=auth_headers
    )
    assert response.status_code == 200


def test_comment_response_includes_commenter_name(client, auth_headers, make_user):
    request_id = _create_request(client, auth_headers)
    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])

    add_response = client.post(
        f"/requests/{request_id}/comments", json={"comment_text": "Looking into it"}, headers=reviewer["headers"]
    )
    added_name = add_response.json()["commenter_name"]
    assert added_name

    list_response = client.get(f"/requests/{request_id}/comments", headers=auth_headers)
    comments = list_response.json()
    assert len(comments) == 1
    assert comments[0]["commenter_name"] == added_name
    assert comments[0]["commenter_reference"] == reviewer["user_id"]


def test_admin_cannot_comment_on_cancelled_request(client, auth_headers, make_user):
    request_id = _create_request(client, auth_headers)
    client.patch(f"/requests/{request_id}/cancel", headers=auth_headers)

    admin = make_user(role="admin")
    response = client.post(
        f"/requests/{request_id}/comments", json={"comment_text": "trying anyway"}, headers=admin["headers"]
    )
    assert response.status_code == 400


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


def test_owner_cannot_add_comment_to_cancelled_request(client, auth_headers):
    request_id = _create_request(client, auth_headers)
    client.patch(f"/requests/{request_id}/cancel", headers=auth_headers)

    response = client.post(
        f"/requests/{request_id}/comments", json={"comment_text": "still relevant?"}, headers=auth_headers
    )
    assert response.status_code == 400

    list_response = client.get(f"/requests/{request_id}/comments", headers=auth_headers)
    assert list_response.json() == []


def test_comments_returned_in_chronological_order(client, auth_headers):
    request_id = _create_request(client, auth_headers)
    client.post(f"/requests/{request_id}/comments", json={"comment_text": "first"}, headers=auth_headers)
    client.post(f"/requests/{request_id}/comments", json={"comment_text": "second"}, headers=auth_headers)

    response = client.get(f"/requests/{request_id}/comments", headers=auth_headers)
    texts = [c["comment_text"] for c in response.json()]
    assert texts == ["first", "second"]


def test_list_comments_query_count_does_not_grow_with_distinct_commenters(client, auth_headers, make_user, db_session):
    """Guards the batched commenter-name lookup in list_comments_for_request:
    the number of SQL statements GET /requests/{id}/comments issues should be
    the same whether 1 or 3 distinct people have commented, not one extra
    query per distinct commenter. (make_user logs in via the real /login
    route, which is rate-limited, so this stays well under that cap rather
    than creating a large number of commenters.)"""
    request_id = _create_request(client, auth_headers)
    engine = db_session.get_bind()

    first_admin = make_user(role="admin")
    client.post(f"/requests/{request_id}/comments", json={"comment_text": "note"}, headers=first_admin["headers"])
    count_with_one_commenter = _count_queries(
        engine, lambda: client.get(f"/requests/{request_id}/comments", headers=auth_headers)
    )

    for admin in (make_user(role="admin"), make_user(role="admin")):
        client.post(f"/requests/{request_id}/comments", json={"comment_text": "note"}, headers=admin["headers"])
    count_with_three_commenters = _count_queries(
        engine, lambda: client.get(f"/requests/{request_id}/comments", headers=auth_headers)
    )

    assert count_with_one_commenter == count_with_three_commenters
