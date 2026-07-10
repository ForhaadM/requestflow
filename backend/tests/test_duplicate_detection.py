import json
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from anthropic import APIConnectionError

import duplicate_detection
from duplicate_detection import check_similar_requests


def _json_response(payload: dict):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(payload))])


def test_check_similar_endpoint_requires_auth(client):
    response = client.post("/requests/check-similar", json={"request_type": "hardware", "description": "x"})
    assert response.status_code == 401


def test_check_similar_description_too_long_rejected(client, auth_headers):
    response = client.post(
        "/requests/check-similar",
        json={"request_type": "hardware", "description": "x" * 501},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_check_similar_no_candidates_skips_api_call(client, auth_headers):
    with patch.object(duplicate_detection._client.messages, "create") as mock_create:
        response = client.post(
            "/requests/check-similar",
            json={"request_type": "hardware", "description": "New monitor please"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json() == {"matches": []}
    mock_create.assert_not_called()


def test_check_similar_returns_high_confidence_match(client, auth_headers):
    create_response = client.post(
        "/requests",
        json={"request_type": "hardware", "description": "Laptop won't turn on"},
        headers=auth_headers,
    )
    existing_id = create_response.json()["request_id"]

    mock_response = _json_response({"matches": [{"request_id": existing_id, "confidence": "high"}]})
    with patch.object(duplicate_detection._client.messages, "create", return_value=mock_response):
        response = client.post(
            "/requests/check-similar",
            json={"request_type": "hardware", "description": "Computer not powering on"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    matches = response.json()["matches"]
    assert len(matches) == 1
    assert matches[0]["request_id"] == existing_id
    assert matches[0]["confidence"] == "high"


def test_check_similar_drops_low_confidence_matches(client, auth_headers):
    create_response = client.post(
        "/requests", json={"request_type": "hardware", "description": "Old request"}, headers=auth_headers
    )
    existing_id = create_response.json()["request_id"]

    mock_response = _json_response({"matches": [{"request_id": existing_id, "confidence": "low"}]})
    with patch.object(duplicate_detection._client.messages, "create", return_value=mock_response):
        response = client.post(
            "/requests/check-similar",
            json={"request_type": "hardware", "description": "Unrelated thing"},
            headers=auth_headers,
        )

    assert response.json() == {"matches": []}


def test_check_similar_excludes_other_users_requests(client, auth_headers, make_user):
    other = make_user(role="requester")
    client.post(
        "/requests", json={"request_type": "hardware", "description": "Other user's broken laptop"}, headers=other["headers"]
    )

    with patch.object(duplicate_detection._client.messages, "create") as mock_create:
        client.post(
            "/requests/check-similar",
            json={"request_type": "hardware", "description": "My laptop is broken"},
            headers=auth_headers,
        )

    # No candidates for this user -> API is never even called.
    mock_create.assert_not_called()


def test_check_similar_excludes_resolved_requests(client, auth_headers, make_user):
    create_response = client.post(
        "/requests", json={"request_type": "hardware", "description": "Broken keyboard"}, headers=auth_headers
    )
    request_id = create_response.json()["request_id"]

    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{request_id}/claim", headers=reviewer["headers"])
    client.post(
        "/reviews",
        json={"request_reference": request_id, "decision": "APPROVED", "comment_text": "Replaced it"},
        headers=reviewer["headers"],
    )

    with patch.object(duplicate_detection._client.messages, "create") as mock_create:
        response = client.post(
            "/requests/check-similar",
            json={"request_type": "hardware", "description": "Keyboard still broken"},
            headers=auth_headers,
        )

    assert response.json() == {"matches": []}
    mock_create.assert_not_called()


def test_check_similar_fails_open_on_api_error(client, auth_headers):
    client.post("/requests", json={"request_type": "hardware", "description": "Something"}, headers=auth_headers)

    fake_request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    with patch.object(
        duplicate_detection._client.messages, "create", side_effect=APIConnectionError(request=fake_request)
    ):
        response = client.post(
            "/requests/check-similar",
            json={"request_type": "hardware", "description": "Something similar"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json() == {"matches": []}


def test_check_similar_scoped_to_open_and_in_progress(db_session, auth_headers, client, make_user):
    open_resp = client.post(
        "/requests", json={"request_type": "software", "description": "Need IDE license"}, headers=auth_headers
    )
    open_id = open_resp.json()["request_id"]

    in_progress_resp = client.post(
        "/requests", json={"request_type": "software", "description": "Need editor license"}, headers=auth_headers
    )
    in_progress_id = in_progress_resp.json()["request_id"]
    reviewer = make_user(role="reviewer")
    client.patch(f"/requests/{in_progress_id}/claim", headers=reviewer["headers"])

    mock_response = _json_response(
        {
            "matches": [
                {"request_id": open_id, "confidence": "high"},
                {"request_id": in_progress_id, "confidence": "medium"},
            ]
        }
    )
    with patch.object(duplicate_detection._client.messages, "create", return_value=mock_response) as mock_create:
        response = client.post(
            "/requests/check-similar",
            json={"request_type": "software", "description": "IDE license request"},
            headers=auth_headers,
        )

    # Both the still-open and the in-progress request should be offered as candidates.
    sent_prompt = mock_create.call_args.kwargs["messages"][0]["content"]
    assert f"id={open_id}" in sent_prompt
    assert f"id={in_progress_id}" in sent_prompt

    matches = response.json()["matches"]
    assert {m["request_id"] for m in matches} == {open_id, in_progress_id}
