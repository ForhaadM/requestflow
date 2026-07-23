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
    body = response.json()
    assert len(body["items"]) == 1
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 25
    assert body["total_pages"] == 1


def test_get_my_requests_returns_only_own(client, auth_headers, make_user):
    client.post("/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers)

    other = make_user(role="requester")
    client.post("/requests", json={"request_type": "software", "description": "Test request"}, headers=other["headers"])

    response = client.get("/requests/me", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["request_type"] == "hardware"
    assert body["total"] == 1


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


def test_cancel_request_owner_can_cancel_open_request(client, auth_headers):
    create_response = client.post(
        "/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers
    )
    request_id = create_response.json()["request_id"]

    response = client.patch(f"/requests/{request_id}/cancel", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_cancel_request_forbidden_once_in_progress(client, auth_headers, make_user):
    # A claimed request is being actively worked on by a reviewer, so it can
    # no longer be withdrawn out from under them — only "open" is cancellable.
    create_response = client.post(
        "/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers
    )
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])

    response = client.patch(f"/requests/{request_id}/cancel", headers=auth_headers)
    assert response.status_code == 400

    check = client.get(f"/requests/{request_id}", headers=auth_headers)
    assert check.json()["status"] == "in-progress"


def test_cancel_request_not_found(client, auth_headers):
    response = client.patch("/requests/9999/cancel", headers=auth_headers)
    assert response.status_code == 404


def test_cancel_request_forbidden_for_other_user(client, auth_headers, make_user):
    create_response = client.post(
        "/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers
    )
    request_id = create_response.json()["request_id"]

    other = make_user(role="requester")
    response = client.patch(f"/requests/{request_id}/cancel", headers=other["headers"])
    assert response.status_code == 403

    check = client.get(f"/requests/{request_id}", headers=auth_headers)
    assert check.json()["status"] == "open"


def test_cancel_request_forbidden_for_reviewer_and_admin(client, auth_headers, make_user):
    # Cancelling is a requester-only action on their own request — a
    # reviewer/admin trying to cancel someone else's request should be
    # rejected the same as any other non-owner, not granted access by role.
    create_response = client.post(
        "/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers
    )
    request_id = create_response.json()["request_id"]

    admin = make_user(role="admin")
    response = client.patch(f"/requests/{request_id}/cancel", headers=admin["headers"])
    assert response.status_code == 403


def test_cancel_request_forbidden_once_decided(client, auth_headers, make_user):
    create_response = client.post(
        "/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers
    )
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews", json={"request_reference": request_id, "decision": "APPROVED"}, headers=reviewer["headers"]
    )

    response = client.patch(f"/requests/{request_id}/cancel", headers=auth_headers)
    assert response.status_code == 400

    check = client.get(f"/requests/{request_id}", headers=auth_headers)
    assert check.json()["status"] == "approved"


def test_cancel_request_forbidden_when_already_cancelled(client, auth_headers):
    create_response = client.post(
        "/requests", json={"request_type": "hardware", "description": "Test request"}, headers=auth_headers
    )
    request_id = create_response.json()["request_id"]

    client.patch(f"/requests/{request_id}/cancel", headers=auth_headers)
    response = client.patch(f"/requests/{request_id}/cancel", headers=auth_headers)
    assert response.status_code == 400


# --- GET /requests search + filters ---------------------------------------


def _seed_requests(client, make_user):
    """Two requesters, each with one request, for search/filter tests."""
    rita = make_user(role="requester")
    # make_user names are "User <Letter>" (A, B, C, ...); register a
    # search-friendly name/email pair directly instead of relying on that.
    client.post(
        "/users",
        json={"name": "Rita Printer", "email": "rita.printer@example.com", "password": "Password123!", "role": "requester"},
    )
    rita_login = client.post("/login", json={"email": "rita.printer@example.com", "password": "Password123!"})
    rita_headers = {"Authorization": f"Bearer {rita_login.json()['access_token']}"}

    client.post(
        "/users",
        json={"name": "Sam Software", "email": "sam.software@example.com", "password": "Password123!", "role": "requester"},
    )
    sam_login = client.post("/login", json={"email": "sam.software@example.com", "password": "Password123!"})
    sam_headers = {"Authorization": f"Bearer {sam_login.json()['access_token']}"}

    rita_req = client.post(
        "/requests",
        json={"request_type": "hardware", "description": "Need a new printer for the office", "priority": "P1"},
        headers=rita_headers,
    ).json()
    sam_req = client.post(
        "/requests",
        json={"request_type": "software", "description": "Need Photoshop license", "priority": "P2"},
        headers=sam_headers,
    ).json()
    return rita_req, sam_req


def test_search_matches_by_request_id_exact(client, make_user):
    rita_req, sam_req = _seed_requests(client, make_user)
    reviewer = make_user(role="reviewer")

    response = client.get(f"/requests?search={rita_req['request_id']}", headers=reviewer["headers"])
    assert response.status_code == 200
    ids = [r["request_id"] for r in response.json()["items"]]
    assert ids == [rita_req["request_id"]]


def test_search_matches_by_requester_name(client, make_user):
    rita_req, sam_req = _seed_requests(client, make_user)
    reviewer = make_user(role="reviewer")

    response = client.get("/requests?search=Printer", headers=reviewer["headers"])
    ids = {r["request_id"] for r in response.json()["items"]}
    assert ids == {rita_req["request_id"]}


def test_search_matches_by_requester_email(client, make_user):
    rita_req, sam_req = _seed_requests(client, make_user)
    reviewer = make_user(role="reviewer")

    response = client.get("/requests?search=sam.software@example.com", headers=reviewer["headers"])
    ids = {r["request_id"] for r in response.json()["items"]}
    assert ids == {sam_req["request_id"]}


def test_search_matches_by_description_substring(client, make_user):
    rita_req, sam_req = _seed_requests(client, make_user)
    reviewer = make_user(role="reviewer")

    response = client.get("/requests?search=Photoshop", headers=reviewer["headers"])
    ids = {r["request_id"] for r in response.json()["items"]}
    assert ids == {sam_req["request_id"]}


def test_filter_by_status_and_priority_independently(client, make_user):
    rita_req, sam_req = _seed_requests(client, make_user)
    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{rita_req['request_id']}/claim", headers=reviewer["headers"])

    status_response = client.get("/requests?status=in-progress", headers=reviewer["headers"])
    assert {r["request_id"] for r in status_response.json()["items"]} == {rita_req["request_id"]}

    priority_response = client.get("/requests?priority=P2", headers=reviewer["headers"])
    assert {r["request_id"] for r in priority_response.json()["items"]} == {sam_req["request_id"]}


def test_filter_combines_with_search(client, make_user):
    rita_req, sam_req = _seed_requests(client, make_user)
    reviewer = make_user(role="reviewer")

    # Search matches both (both descriptions contain "Need"), but the type
    # filter should narrow it down to just the hardware one.
    response = client.get("/requests?search=Need&request_type=hardware", headers=reviewer["headers"])
    ids = {r["request_id"] for r in response.json()["items"]}
    assert ids == {rita_req["request_id"]}

    # A filter with no matching search result returns nothing.
    empty = client.get("/requests?search=Photoshop&request_type=hardware", headers=reviewer["headers"])
    assert empty.json()["items"] == []
    assert empty.json()["total"] == 0


def test_multiple_status_values_are_ored(client, make_user):
    rita_req, sam_req = _seed_requests(client, make_user)
    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{rita_req['request_id']}/claim", headers=reviewer["headers"])

    response = client.get("/requests?status=in-progress&status=open", headers=reviewer["headers"])
    ids = {r["request_id"] for r in response.json()["items"]}
    assert ids == {rita_req["request_id"], sam_req["request_id"]}


def test_search_and_filters_return_same_results_for_reviewer_and_admin(client, make_user):
    # GET /requests has no differential role-scoping between reviewer and
    # admin today (both see every request) — search/filters must not
    # introduce one by accident.
    rita_req, sam_req = _seed_requests(client, make_user)
    reviewer = make_user(role="reviewer")
    admin = make_user(role="admin")

    reviewer_response = client.get("/requests?search=Need&priority=P1", headers=reviewer["headers"])
    admin_response = client.get("/requests?search=Need&priority=P1", headers=admin["headers"])

    reviewer_ids = {r["request_id"] for r in reviewer_response.json()["items"]}
    admin_ids = {r["request_id"] for r in admin_response.json()["items"]}
    assert reviewer_ids == admin_ids == {rita_req["request_id"]}


def test_search_still_forbidden_for_requester(client, auth_headers):
    response = client.get("/requests?search=anything", headers=auth_headers)
    assert response.status_code == 403


# --- GET /requests pagination ----------------------------------------------


def _create_n_requests(client, headers, n, priority="P1"):
    return [
        client.post(
            "/requests",
            json={"request_type": "hardware", "description": f"Request {i}", "priority": priority},
            headers=headers,
        ).json()
        for i in range(n)
    ]


def test_pagination_defaults(client, auth_headers, make_user):
    _create_n_requests(client, auth_headers, 3)
    admin = make_user(role="admin")

    response = client.get("/requests", headers=admin["headers"])
    body = response.json()
    assert len(body["items"]) == 3
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 25
    assert body["total_pages"] == 1


def test_pagination_slices_the_filtered_set(client, auth_headers, make_user):
    created = _create_n_requests(client, auth_headers, 5)
    admin = make_user(role="admin")

    page1 = client.get("/requests?page=1&page_size=2", headers=admin["headers"]).json()
    page2 = client.get("/requests?page=2&page_size=2", headers=admin["headers"]).json()
    page3 = client.get("/requests?page=3&page_size=2", headers=admin["headers"]).json()

    assert page1["total"] == page2["total"] == page3["total"] == 5
    assert page1["total_pages"] == page2["total_pages"] == page3["total_pages"] == 3
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2
    assert len(page3["items"]) == 1

    # Newest-first by default, and no row should appear on two pages.
    all_ids = [r["request_id"] for r in page1["items"] + page2["items"] + page3["items"]]
    assert all_ids == sorted((c["request_id"] for c in created), reverse=True)


def test_pagination_out_of_range_page_returns_empty_items(client, auth_headers, make_user):
    _create_n_requests(client, auth_headers, 2)
    admin = make_user(role="admin")

    response = client.get("/requests?page=999&page_size=10", headers=admin["headers"])
    body = response.json()
    assert response.status_code == 200
    assert body["items"] == []
    assert body["total"] == 2
    assert body["page"] == 999


def test_pagination_page_size_capped_at_100(client, auth_headers, make_user):
    admin = make_user(role="admin")

    response = client.get("/requests?page_size=101", headers=admin["headers"])
    assert response.status_code == 422

    response = client.get("/requests?page_size=100", headers=admin["headers"])
    assert response.status_code == 200
    assert response.json()["page_size"] == 100


def test_pagination_page_must_be_at_least_one(client, auth_headers, make_user):
    admin = make_user(role="admin")

    response = client.get("/requests?page=0", headers=admin["headers"])
    assert response.status_code == 422


def test_pagination_applies_to_filtered_set_not_whole_table(client, make_user):
    rita_req, sam_req = _seed_requests(client, make_user)
    reviewer = make_user(role="reviewer")

    response = client.get("/requests?request_type=hardware&page_size=1", headers=reviewer["headers"])
    body = response.json()
    assert body["total"] == 1
    assert body["total_pages"] == 1
    assert [r["request_id"] for r in body["items"]] == [rita_req["request_id"]]


def test_sort_by_priority_ascending_and_descending(client, make_user):
    rita_req, sam_req = _seed_requests(client, make_user)  # P1, P2
    reviewer = make_user(role="reviewer")

    asc = client.get("/requests?sort=priority&sort_dir=asc", headers=reviewer["headers"]).json()
    assert [r["request_id"] for r in asc["items"]] == [rita_req["request_id"], sam_req["request_id"]]

    desc = client.get("/requests?sort=priority&sort_dir=desc", headers=reviewer["headers"]).json()
    assert [r["request_id"] for r in desc["items"]] == [sam_req["request_id"], rita_req["request_id"]]


def test_sort_defaults_to_newest_created_first(client, auth_headers, make_user):
    created = _create_n_requests(client, auth_headers, 3)
    admin = make_user(role="admin")

    response = client.get("/requests", headers=admin["headers"]).json()
    assert [r["request_id"] for r in response["items"]] == sorted(
        (c["request_id"] for c in created), reverse=True
    )


def test_requests_me_pagination(client, auth_headers):
    _create_n_requests(client, auth_headers, 3)

    response = client.get("/requests/me?page=1&page_size=2", headers=auth_headers)
    body = response.json()
    assert body["total"] == 3
    assert body["total_pages"] == 2
    assert len(body["items"]) == 2

    response = client.get("/requests/me?page=2&page_size=2", headers=auth_headers)
    body = response.json()
    assert len(body["items"]) == 1


# --- GET /requests/summary --------------------------------------------------


def test_requests_summary_counts(client, make_user):
    rita_req, sam_req = _seed_requests(client, make_user)  # hardware/P1, software/P2
    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{rita_req['request_id']}/claim", headers=reviewer["headers"])

    response = client.get("/requests/summary", headers=reviewer["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["by_status"] == {"open": 1, "in-progress": 1}
    assert body["by_type"] == {"hardware": 1, "software": 1}
    assert body["claimed_by_me"] == 1


def test_requests_summary_respects_search_and_priority_filters(client, make_user):
    rita_req, sam_req = _seed_requests(client, make_user)  # hardware/P1, software/P2
    reviewer = make_user(role="reviewer")

    response = client.get("/requests/summary?priority=P2", headers=reviewer["headers"])
    body = response.json()
    assert body["total"] == 1
    assert body["by_type"] == {"software": 1}


def test_requests_summary_forbidden_for_requester(client, auth_headers):
    response = client.get("/requests/summary", headers=auth_headers)
    assert response.status_code == 403
