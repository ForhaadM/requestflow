from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

import chatbot
from rate_limit import enforce_rate_limit


def _text_response(text):
    return SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=text)],
    )


def test_enforce_rate_limit_allows_up_to_max():
    for _ in range(3):
        enforce_rate_limit("unit-test-key-a", max_requests=3, window_seconds=60)


def test_enforce_rate_limit_blocks_after_max():
    for _ in range(3):
        enforce_rate_limit("unit-test-key-b", max_requests=3, window_seconds=60)
    with pytest.raises(HTTPException) as exc_info:
        enforce_rate_limit("unit-test-key-b", max_requests=3, window_seconds=60)
    assert exc_info.value.status_code == 429


def test_enforce_rate_limit_keys_are_independent():
    for _ in range(3):
        enforce_rate_limit("unit-test-key-c", max_requests=3, window_seconds=60)
    # A different key has its own, unaffected budget.
    enforce_rate_limit("unit-test-key-d", max_requests=3, window_seconds=60)


def test_login_rate_limited_after_repeated_attempts(client, registered_user, test_credentials):
    for _ in range(5):
        response = client.post(
            "/login", json={"email": test_credentials["email"], "password": "wrongpassword"}
        )
        assert response.status_code == 400

    response = client.post(
        "/login", json={"email": test_credentials["email"], "password": "wrongpassword"}
    )
    assert response.status_code == 429


def test_chat_rate_limited_after_repeated_messages(client, auth_headers):
    with patch.object(chatbot._client.messages, "create", return_value=_text_response("hi")):
        for _ in range(20):
            response = client.post("/chat", json={"message": "hi", "history": []}, headers=auth_headers)
            assert response.status_code == 200

        response = client.post("/chat", json={"message": "hi", "history": []}, headers=auth_headers)

    assert response.status_code == 429
