from types import SimpleNamespace
from unittest.mock import patch

import httpx
from anthropic import APIConnectionError

import chatbot
from models import Requests


def _text_response(text):
    return SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=text)],
    )


def _tool_use_response(tool_name, tool_input, tool_id="toolu_1"):
    return SimpleNamespace(
        stop_reason="tool_use",
        content=[SimpleNamespace(type="tool_use", name=tool_name, input=tool_input, id=tool_id)],
    )


def test_chat_requires_auth(client):
    response = client.post("/chat", json={"message": "hi", "history": []})
    assert response.status_code == 401


def test_chat_message_too_long_rejected(client, auth_headers):
    response = client.post(
        "/chat", json={"message": "x" * 2001, "history": []}, headers=auth_headers
    )
    assert response.status_code == 422


def test_chat_history_too_long_rejected(client, auth_headers):
    oversized_history = [{"role": "user", "content": "hi"} for _ in range(41)]
    response = client.post(
        "/chat", json={"message": "hi", "history": oversized_history}, headers=auth_headers
    )
    assert response.status_code == 422


def test_chat_simple_reply(client, auth_headers):
    with patch.object(chatbot._client.messages, "create", return_value=_text_response("Hello there!")) as mock_create:
        response = client.post("/chat", json={"message": "hi", "history": []}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Hello there!"
    assert body["history"][-1] == {"role": "assistant", "content": "Hello there!"}
    assert body["history"][-2] == {"role": "user", "content": "hi"}
    # No request was created on this turn, so the client shouldn't be told to refresh its lists.
    assert body["request_created"] is False
    mock_create.assert_called_once()


def test_chat_create_request_tool_call(client, auth_headers, db_session):
    tool_call = _tool_use_response(
        "create_request",
        {"request_type": "hardware", "description": "New monitor", "priority": "P1"},
    )
    final = _text_response("I've created your hardware request.")

    with patch.object(chatbot._client.messages, "create", side_effect=[tool_call, final]):
        response = client.post(
            "/chat",
            json={"message": "I need a new monitor", "history": []},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "I've created your hardware request."
    # Signals the client to refresh My Requests / Review Queue / etc. — this
    # is what fixes those lists not updating live after a chatbot-created request.
    assert body["request_created"] is True

    created = db_session.query(Requests).filter(Requests.description == "New monitor").first()
    assert created is not None
    assert created.request_type == "hardware"
    assert created.priority == "P1"


def test_chat_create_request_validation_error_surfaces_to_model(client, auth_headers):
    # P0 without a justification should fail validation inside the tool, not create a row.
    tool_call = _tool_use_response(
        "create_request",
        {"request_type": "hardware", "description": "Broken laptop", "priority": "P0"},
    )
    final = _text_response("You'll need to give me a justification for that urgency level.")

    with patch.object(chatbot._client.messages, "create", side_effect=[tool_call, final]) as mock_create:
        response = client.post(
            "/chat",
            json={"message": "My laptop is broken, very urgent", "history": []},
            headers=auth_headers,
        )

    assert response.status_code == 200
    # second call's tool_result should carry the validation error back to the model
    second_call_messages = mock_create.call_args_list[1].kwargs["messages"]
    tool_result_content = second_call_messages[-1]["content"][0]
    assert tool_result_content["is_error"] is True
    assert "justification" in tool_result_content["content"]


def test_chat_get_request_status_respects_ownership(client, auth_headers, make_user):
    create_response = client.post(
        "/requests",
        json={"request_type": "hardware", "description": "Owner's request"},
        headers=auth_headers,
    )
    request_id = create_response.json()["request_id"]

    other = make_user(role="requester")
    tool_call = _tool_use_response("get_request_status", {"request_id": request_id})
    final = _text_response("I couldn't find that request for you.")

    with patch.object(chatbot._client.messages, "create", side_effect=[tool_call, final]) as mock_create:
        response = client.post(
            "/chat",
            json={"message": f"what's the status of request {request_id}", "history": []},
            headers=other["headers"],
        )

    assert response.status_code == 200
    second_call_messages = mock_create.call_args_list[1].kwargs["messages"]
    tool_result_content = second_call_messages[-1]["content"][0]
    assert tool_result_content["is_error"] is True
    assert "Not Authorized" in tool_result_content["content"]


def test_chat_handles_api_error_gracefully(client, auth_headers):
    fake_request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    with patch.object(
        chatbot._client.messages,
        "create",
        side_effect=APIConnectionError(request=fake_request),
    ):
        response = client.post("/chat", json={"message": "hi", "history": []}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["reply"] == chatbot.UNAVAILABLE_MESSAGE


def test_chat_handles_api_error_mid_conversation_gracefully(client, auth_headers, db_session):
    fake_request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    tool_call = _tool_use_response(
        "create_request",
        {"request_type": "hardware", "description": "New monitor", "priority": "P1"},
    )

    with patch.object(
        chatbot._client.messages,
        "create",
        side_effect=[tool_call, APIConnectionError(request=fake_request)],
    ):
        response = client.post(
            "/chat",
            json={"message": "I need a new monitor", "history": []},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json()["reply"] == chatbot.UNAVAILABLE_MESSAGE
    # the tool call itself had already succeeded before the second API call failed
    created = db_session.query(Requests).filter(Requests.description == "New monitor").first()
    assert created is not None


def test_chat_create_request_blocks_on_duplicate_and_reports_it(client, auth_headers, db_session):
    tool_call = _tool_use_response(
        "create_request",
        {"request_type": "hardware", "description": "Printer still not working", "priority": "P1"},
    )
    final = _text_response("This looks similar to request #47 ('printer not working'). Still want me to create it?")

    fake_match = [
        {
            "request_id": 47,
            "request_type": "hardware",
            "description": "printer not working",
            "priority": "P1",
            "status": "open",
            "created_at": "2026-07-08T00:00:00",
            "confidence": "high",
        }
    ]

    with patch.object(chatbot, "check_similar_requests", return_value=fake_match):
        with patch.object(chatbot._client.messages, "create", side_effect=[tool_call, final]) as mock_create:
            response = client.post(
                "/chat",
                json={"message": "The printer is still broken", "history": []},
                headers=auth_headers,
            )

    assert response.status_code == 200
    # not created — the tool returned a duplicate_warning instead, so the
    # client shouldn't be told to refresh its lists for a non-event
    assert response.json()["request_created"] is False
    created = db_session.query(Requests).filter(Requests.description == "Printer still not working").first()
    assert created is None

    second_call_messages = mock_create.call_args_list[1].kwargs["messages"]
    tool_result_content = second_call_messages[-1]["content"][0]
    assert tool_result_content["is_error"] is False
    assert "duplicate_warning" in tool_result_content["content"]
    assert "47" in tool_result_content["content"]


def test_chat_create_request_menu_intent_skips_the_llm_call(client, auth_headers):
    with patch.object(chatbot._client.messages, "create") as mock_create:
        response = client.post(
            "/chat",
            json={"message": "I want to create a new request.", "history": [], "intent": "create_request_menu"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == chatbot.CREATE_REQUEST_MENU_REPLY
    assert "1. Hardware" in body["reply"]
    mock_create.assert_not_called()


def test_chat_type_selection_by_number_resolves_correctly(client, auth_headers):
    history = [
        {"role": "user", "content": "I want to create a new request."},
        {"role": "assistant", "content": chatbot.CREATE_REQUEST_MENU_REPLY},
    ]
    final = _text_response("Got it, a software request. How urgent is this?")

    with patch.object(chatbot._client.messages, "create", return_value=final) as mock_create:
        response = client.post(
            "/chat",
            json={"message": "2", "history": history},
            headers=auth_headers,
        )

    assert response.status_code == 200
    sent_messages = mock_create.call_args.kwargs["messages"]
    assert sent_messages[-1]["content"] == "I'd like to create a Software request."
    # the raw reply the user actually typed is preserved in the returned history, not the rewrite
    assert response.json()["history"][-2] == {"role": "user", "content": "2"}


def test_chat_type_selection_by_name_resolves_correctly(client, auth_headers):
    history = [
        {"role": "user", "content": "I want to create a new request."},
        {"role": "assistant", "content": chatbot.CREATE_REQUEST_MENU_REPLY},
    ]
    final = _text_response("Got it, a bug report. How urgent is this?")

    with patch.object(chatbot._client.messages, "create", return_value=final) as mock_create:
        response = client.post(
            "/chat",
            json={"message": "bug-report", "history": history},
            headers=auth_headers,
        )

    assert response.status_code == 200
    sent_messages = mock_create.call_args.kwargs["messages"]
    assert sent_messages[-1]["content"] == "I'd like to create a Bug Report request."


def test_chat_unrecognized_reply_to_menu_falls_back_to_raw_message(client, auth_headers):
    history = [
        {"role": "user", "content": "I want to create a new request."},
        {"role": "assistant", "content": chatbot.CREATE_REQUEST_MENU_REPLY},
    ]
    final = _text_response("I'm not sure I understood that — could you pick a number 1-9?")

    with patch.object(chatbot._client.messages, "create", return_value=final) as mock_create:
        response = client.post(
            "/chat",
            json={"message": "not a valid option", "history": history},
            headers=auth_headers,
        )

    assert response.status_code == 200
    sent_messages = mock_create.call_args.kwargs["messages"]
    assert sent_messages[-1]["content"] == "not a valid option"


def test_chat_create_request_confirmed_duplicate_bypasses_check(client, auth_headers, db_session):
    tool_call = _tool_use_response(
        "create_request",
        {
            "request_type": "hardware",
            "description": "Printer still not working",
            "priority": "P1",
            "confirmed_duplicate": True,
        },
    )
    final = _text_response("Done — created a new request anyway.")

    with patch.object(chatbot, "check_similar_requests") as mock_check:
        with patch.object(chatbot._client.messages, "create", side_effect=[tool_call, final]):
            response = client.post(
                "/chat",
                json={"message": "Yes, create it anyway", "history": []},
                headers=auth_headers,
            )

    assert response.status_code == 200
    mock_check.assert_not_called()

    created = db_session.query(Requests).filter(Requests.description == "Printer still not working").first()
    assert created is not None
