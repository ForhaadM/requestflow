def test_claim_open_request_succeeds(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    response = client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in-progress"
    assert body["claimed_by"] == reviewer["user_id"]


def test_claim_forbidden_for_requester(client, auth_headers):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    response = client.patch(f"/requests/{request_id}/claim", headers=auth_headers)
    assert response.status_code == 403


def test_claim_already_claimed_fails(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer_one = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer_one["headers"])

    reviewer_two = make_user(role="reviewer")
    response = client.patch(f"/requests/{request_id}/claim", headers=reviewer_two["headers"])
    assert response.status_code == 400


def test_unclaim_by_claimant_succeeds(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])

    response = client.patch(f"/requests/{request_id}/unclaim", headers=reviewer["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "open"
    assert body["claimed_by"] is None


def test_unclaim_by_other_reviewer_forbidden(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer_one = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer_one["headers"])

    reviewer_two = make_user(role="reviewer")
    response = client.patch(f"/requests/{request_id}/unclaim", headers=reviewer_two["headers"])
    assert response.status_code == 403


def test_unclaim_by_admin_succeeds(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])

    admin = make_user(role="admin")
    response = client.patch(f"/requests/{request_id}/unclaim", headers=admin["headers"])
    assert response.status_code == 200


def test_review_without_claim_fails(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    response = client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
    )
    assert response.status_code == 400


def test_review_by_non_claimant_reviewer_forbidden(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer_one = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer_one["headers"])

    reviewer_two = make_user(role="reviewer")
    response = client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer_two["headers"]
    )
    assert response.status_code == 403


def test_approve_sets_status_approved(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
    )

    response = client.get(f"/requests/{request_id}", headers=auth_headers)
    assert response.json()["status"] == "approved"


def test_reject_sets_status_rejected(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "NOT APPROVED", "comment_text": "Not needed"},
        headers=reviewer["headers"],
    )

    response = client.get(f"/requests/{request_id}", headers=auth_headers)
    assert response.json()["status"] == "rejected"


def test_admin_can_override_rejected_request(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "NOT APPROVED", "comment_text": "Not needed"},
        headers=reviewer["headers"],
    )

    admin = make_user(role="admin")
    override_response = client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "APPROVED", "comment_text": "Reconsidered"},
        headers=admin["headers"],
    )
    assert override_response.status_code == 200

    response = client.get(f"/requests/{request_id}", headers=auth_headers)
    assert response.json()["status"] == "approved"


def test_override_requires_comment(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "NOT APPROVED", "comment_text": "Not needed"},
        headers=reviewer["headers"],
    )

    admin = make_user(role="admin")
    response = client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "APPROVED"},
        headers=admin["headers"],
    )
    assert response.status_code == 400


def test_reviewer_cannot_override_rejected_request(client, auth_headers, make_user):
    create_response = client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "NOT APPROVED", "comment_text": "Not needed"},
        headers=reviewer["headers"],
    )

    other_reviewer = make_user(role="reviewer")
    response = client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "APPROVED", "comment_text": "trying to override"},
        headers=other_reviewer["headers"],
    )
    assert response.status_code == 403


def test_approving_bug_report_without_resolution_notes_fails(client, auth_headers, make_user):
    create_response = client.post(
        "/requests", json={"request_type": "bug-report", "description": "Checkout page crashes"}, headers=auth_headers
    )
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    response = client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
    )
    assert response.status_code == 400


def test_approving_bug_report_with_resolution_notes_succeeds(client, auth_headers, make_user):
    create_response = client.post(
        "/requests", json={"request_type": "bug-report", "description": "Checkout page crashes"}, headers=auth_headers
    )
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    response = client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "APPROVED", "comment_text": "Fixed null check in checkout handler"},
        headers=reviewer["headers"],
    )
    assert response.status_code == 200


def test_approving_hardware_request_without_comment_succeeds(client, auth_headers, make_user):
    create_response = client.post(
        "/requests", json={"request_type": "hardware", "description": "Need a monitor"}, headers=auth_headers
    )
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    response = client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
    )
    assert response.status_code == 200


def test_admin_can_reverse_an_approval(client, auth_headers, make_user):
    create_response = client.post(
        "/requests", json={"request_type": "hardware", "description": "Need a monitor"}, headers=auth_headers
    )
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
    )

    admin = make_user(role="admin")
    response = client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "NOT APPROVED", "comment_text": "Approved in error, reversing"},
        headers=admin["headers"],
    )
    assert response.status_code == 200

    check = client.get(f"/requests/{request_id}", headers=auth_headers)
    assert check.json()["status"] == "rejected"


def test_reviewer_cannot_reverse_an_approval(client, auth_headers, make_user):
    create_response = client.post(
        "/requests", json={"request_type": "hardware", "description": "Need a monitor"}, headers=auth_headers
    )
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
    )

    other_reviewer = make_user(role="reviewer")
    response = client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "NOT APPROVED", "comment_text": "trying to reverse"},
        headers=other_reviewer["headers"],
    )
    assert response.status_code == 403


def test_reversing_an_approval_requires_comment(client, auth_headers, make_user):
    create_response = client.post(
        "/requests", json={"request_type": "hardware", "description": "Need a monitor"}, headers=auth_headers
    )
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
    )

    admin = make_user(role="admin")
    response = client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "NOT APPROVED"},
        headers=admin["headers"],
    )
    assert response.status_code == 400


def test_create_request_invalid_type_rejected(client, auth_headers):
    response = client.post(
        "/requests", json={"request_type": "not-a-real-type", "description": "test"}, headers=auth_headers
    )
    assert response.status_code == 422


def test_create_request_invalid_priority_rejected(client, auth_headers):
    response = client.post(
        "/requests", json={"request_type": "hardware", "description": "test", "priority": "P9"}, headers=auth_headers
    )
    assert response.status_code == 422


def test_create_review_invalid_decision_rejected(client, auth_headers, make_user):
    create_response = client.post(
        "/requests", json={"request_type": "hardware", "description": "test"}, headers=auth_headers
    )
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    response = client.post(
        "/reviews", json={"request_reference": request_id, "decision": "MAYBE"}, headers=reviewer["headers"]
    )
    assert response.status_code == 422


def test_request_reviews_are_returned_in_chronological_order(client, auth_headers, make_user):
    create_response = client.post(
        "/requests", json={"request_type": "hardware", "description": "test"}, headers=auth_headers
    )
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "NOT APPROVED", "comment_text": "first"},
        headers=reviewer["headers"],
    )

    admin = make_user(role="admin")
    client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "APPROVED", "comment_text": "second"},
        headers=admin["headers"],
    )

    response = client.get(f"/requests/{request_id}/reviews", headers=auth_headers)
    reviews = response.json()
    assert [r["comment_text"] for r in reviews] == ["first", "second"]
