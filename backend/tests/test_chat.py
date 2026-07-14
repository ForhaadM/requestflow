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
    # A plain reply isn't a dead end that needs the quick-option buttons back.
    assert body["show_quick_options"] is False
    assert body["in_creation_flow"] is False
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
    # This menu expects a numbered/named selection next, unlike the informational
    # listing, so the client should stay on the text-input state, not show buttons.
    assert body["show_quick_options"] is False
    assert body["in_creation_flow"] is True
    mock_create.assert_not_called()


def test_chat_agreeing_to_create_after_offer_shows_the_type_menu(client, auth_headers):
    # Reproduces the reported bug: "check my requests" -> none found -> model
    # offers to create one -> user says "yes" -> the model must call
    # show_request_type_menu (not free-write "which one do you want to
    # create?" with no options), so the numbered list is never skipped.
    history = [
        {"role": "user", "content": "what's the status of my requests?"},
        {
            "role": "assistant",
            "content": "You don't have any requests yet. Would you like to create one?",
        },
    ]
    tool_call = _tool_use_response("show_request_type_menu", {})

    with patch.object(chatbot._client.messages, "create", return_value=tool_call) as mock_create:
        response = client.post(
            "/chat",
            json={"message": "yes", "history": history},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    # Byte-for-byte the same menu the dedicated button produces — the numbered
    # list is never skipped regardless of which path started the flow.
    assert body["reply"] == chatbot.CREATE_REQUEST_MENU_REPLY
    assert "1. Hardware" in body["reply"]
    assert body["in_creation_flow"] is True
    mock_create.assert_called_once()


def test_chat_type_menu_from_model_path_then_number_reply_resolves_correctly(client, auth_headers):
    # Follow-up to the above: once the model-triggered menu is shown, a plain
    # numbered reply must resolve exactly like the button-triggered menu does
    # — deterministically, with category examples, and with no model call.
    history = [
        {"role": "user", "content": "yes"},
        {"role": "assistant", "content": chatbot.CREATE_REQUEST_MENU_REPLY},
    ]

    with patch.object(chatbot._client.messages, "create") as mock_create:
        response = client.post(
            "/chat",
            json={"message": "2", "history": history, "in_creation_flow": True},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == chatbot._type_selected_reply("software")
    assert "New software license" in body["reply"]
    mock_create.assert_not_called()


def test_chat_type_selection_by_number_resolves_correctly(client, auth_headers):
    history = [
        {"role": "user", "content": "I want to create a new request."},
        {"role": "assistant", "content": chatbot.CREATE_REQUEST_MENU_REPLY},
    ]

    with patch.object(chatbot._client.messages, "create") as mock_create:
        response = client.post(
            "/chat",
            json={"message": "2", "history": history},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    # Deterministic — resolves and shows category examples with no model call.
    assert body["reply"] == chatbot._type_selected_reply("software")
    assert "New software license" in body["reply"]
    assert body["in_creation_flow"] is True
    mock_create.assert_not_called()
    # the raw reply the user actually typed is preserved in the returned history
    assert body["history"][-2] == {"role": "user", "content": "2"}


def test_chat_type_selection_by_name_resolves_correctly(client, auth_headers):
    history = [
        {"role": "user", "content": "I want to create a new request."},
        {"role": "assistant", "content": chatbot.CREATE_REQUEST_MENU_REPLY},
    ]

    with patch.object(chatbot._client.messages, "create") as mock_create:
        response = client.post(
            "/chat",
            json={"message": "bug-report", "history": history},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == chatbot._type_selected_reply("bug-report")
    assert "App crashing" in body["reply"]
    mock_create.assert_not_called()


def test_chat_type_selected_examples_shown_for_every_category(client, auth_headers):
    # The bug report: examples must show consistently for every category, not
    # just the ones covered above.
    history = [
        {"role": "user", "content": "I want to create a new request."},
        {"role": "assistant", "content": chatbot.CREATE_REQUEST_MENU_REPLY},
    ]

    for index, request_type in enumerate(chatbot.REQUEST_TYPES, start=1):
        with patch.object(chatbot._client.messages, "create") as mock_create:
            response = client.post(
                "/chat",
                json={"message": str(index), "history": history},
                headers=auth_headers,
            )
        assert response.status_code == 200
        body = response.json()
        assert body["reply"] == chatbot._type_selected_reply(request_type), f"failed for {request_type!r}"
        for example in chatbot._CATEGORY_EXAMPLES[request_type]:
            assert example in body["reply"]
        mock_create.assert_not_called()


def test_chat_request_type_selected_tool_call_shows_examples(client, auth_headers):
    # The other entry point: the user names a category directly ("I want to
    # submit a hardware request") without going through the numbered menu at
    # all — the model must call request_type_selected instead of free-writing
    # "what do you need?" with no examples.
    tool_call = _tool_use_response("request_type_selected", {"request_type": "hardware"})

    with patch.object(chatbot._client.messages, "create", return_value=tool_call) as mock_create:
        response = client.post(
            "/chat",
            json={"message": "I want to submit a hardware request", "history": []},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == chatbot._type_selected_reply("hardware")
    assert "Laptop or monitor request" in body["reply"]
    assert body["in_creation_flow"] is True
    mock_create.assert_called_once()


def test_chat_ask_urgency_tool_call_shows_deterministic_question(client, auth_headers):
    # Reproduces the reported bug: after the user answers "what do you need?"
    # (here "jira access" for a software request), the model must call
    # ask_urgency before create_request — never silently default the priority.
    history = [
        {"role": "user", "content": "1"},
        {"role": "assistant", "content": chatbot._type_selected_reply("software")},
    ]
    tool_call = _tool_use_response("ask_urgency", {})

    with patch.object(chatbot._client.messages, "create", return_value=tool_call) as mock_create:
        response = client.post(
            "/chat",
            json={"message": "jira access", "history": history, "in_creation_flow": True},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == chatbot.ASK_URGENCY_REPLY
    assert "1. Low" in body["reply"] and "4. Urgent" in body["reply"]
    assert body["request_created"] is False
    assert body["in_creation_flow"] is True
    mock_create.assert_called_once()


def test_chat_create_request_without_priority_is_rejected_by_schema(client, auth_headers, db_session):
    # priority is now a required create_request argument (no schema default,
    # no silent P1 fallback) specifically so the model can't skip asking —
    # simulates what happens if it ever tries to omit it anyway.
    tool_call = _tool_use_response(
        "create_request",
        {"request_type": "software", "description": "jira access"},
    )
    final = _text_response("Something went wrong creating that request.")

    with patch.object(chatbot._client.messages, "create", side_effect=[tool_call, final]) as mock_create:
        response = client.post(
            "/chat",
            json={"message": "jira access", "history": [], "in_creation_flow": True},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json()["request_created"] is False
    created = db_session.query(Requests).filter(Requests.description == "jira access").first()
    assert created is None
    second_call_messages = mock_create.call_args_list[1].kwargs["messages"]
    tool_result_content = second_call_messages[-1]["content"][0]
    assert tool_result_content["is_error"] is True


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


def test_chat_qa_list_request_types_tool_call_returns_distinct_informational_text(client, auth_headers):
    tool_call = _tool_use_response("list_request_types", {})

    with patch.object(chatbot._client.messages, "create", return_value=tool_call) as mock_create:
        response = client.post(
            "/chat",
            json={"message": "what can I submit?", "history": []},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    # Distinct wording from the creation-flow menu — purely informational, not a
    # "what type do you want to create" prompt.
    assert body["reply"] == chatbot.INFO_REQUEST_TYPES_REPLY
    assert body["reply"] != chatbot.CREATE_REQUEST_MENU_REPLY
    assert "These are the types of requests you can make" in body["reply"]
    assert "1. Hardware" in body["reply"]
    # Tells the client to re-show its quick-option buttons, since this
    # informational reply doesn't lead anywhere on its own.
    assert body["show_quick_options"] is True
    # Purely informational — does not start the guided creation flow.
    assert body["in_creation_flow"] is False
    # Only one API call — no second round-trip to let the model phrase its own list.
    mock_create.assert_called_once()


def test_chat_qa_menu_reply_does_not_trigger_type_selection_parsing(client, auth_headers):
    # The informational listing must NOT be treated like the creation-flow menu —
    # a numbered follow-up should go to the model as-is, not get rewritten into
    # "I'd like to create a ... request."
    history = [
        {"role": "user", "content": "what request types are there?"},
        {"role": "assistant", "content": chatbot.INFO_REQUEST_TYPES_REPLY},
    ]
    final = _text_response("Sure, what would you like help with?")

    with patch.object(chatbot._client.messages, "create", return_value=final) as mock_create:
        response = client.post(
            "/chat",
            json={"message": "1", "history": history},
            headers=auth_headers,
        )

    assert response.status_code == 200
    sent_messages = mock_create.call_args.kwargs["messages"]
    assert sent_messages[-1]["content"] == "1"


def test_chat_create_request_menu_reply_with_trailing_dot_resolves_correctly(client, auth_headers):
    # "1." on the dedicated creation-flow menu must still resolve (unlike the
    # informational Q&A path, which doesn't parse numbered replies at all).
    history = [
        {"role": "user", "content": "I want to create a new request."},
        {"role": "assistant", "content": chatbot.CREATE_REQUEST_MENU_REPLY},
    ]

    with patch.object(chatbot._client.messages, "create") as mock_create:
        response = client.post(
            "/chat",
            json={"message": "1.", "history": history},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == chatbot._type_selected_reply("hardware")
    mock_create.assert_not_called()


def test_chat_cancel_at_type_selection_step_via_button(client, auth_headers, db_session):
    # The "Cancel request" bar sends the literal message "cancel" — same as if
    # the user typed it — while the type-selection menu is the last assistant
    # turn, so this is deterministic even without an explicit in_creation_flow
    # flag (the menu text itself is enough to recognize the step).
    history = [
        {"role": "user", "content": "I want to create a new request."},
        {"role": "assistant", "content": chatbot.CREATE_REQUEST_MENU_REPLY},
    ]

    with patch.object(chatbot._client.messages, "create") as mock_create:
        response = client.post(
            "/chat",
            json={"message": "cancel", "history": history, "in_creation_flow": True},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == chatbot.CANCEL_REQUEST_REPLY
    assert body["request_created"] is False
    assert body["show_quick_options"] is True
    assert body["in_creation_flow"] is False
    mock_create.assert_not_called()
    assert db_session.query(Requests).count() == 0


def test_chat_cancel_at_description_step_via_keyword(client, auth_headers, db_session):
    # Cancelling right after the deterministic category-examples reply (a new
    # step introduced with the examples fix) — also a free-form step, so this
    # relies on the in_creation_flow flag same as urgency/justification.
    history = [
        {"role": "user", "content": "1"},
        {"role": "assistant", "content": chatbot._type_selected_reply("hardware")},
    ]

    with patch.object(chatbot._client.messages, "create") as mock_create:
        response = client.post(
            "/chat",
            json={"message": "cancel", "history": history, "in_creation_flow": True},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == chatbot.CANCEL_REQUEST_REPLY
    assert body["show_quick_options"] is True
    assert body["in_creation_flow"] is False
    mock_create.assert_not_called()
    assert db_session.query(Requests).count() == 0


def test_chat_cancel_at_urgency_step_via_keyword(client, auth_headers, db_session):
    # Urgency is a free-form model step, not deterministically tracked — the
    # in_creation_flow flag (sent by the client for the flow's duration) is
    # what lets this be recognized without any server-side step tracking.
    history = [
        {"role": "user", "content": "I'd like to create a Hardware request."},
        {"role": "assistant", "content": "Got it, a hardware request. How urgent is this?\n1. Low\n2. Medium\n3. High\n4. Urgent"},
    ]

    with patch.object(chatbot._client.messages, "create") as mock_create:
        response = client.post(
            "/chat",
            json={"message": "nevermind", "history": history, "in_creation_flow": True},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == chatbot.CANCEL_REQUEST_REPLY
    assert body["show_quick_options"] is True
    mock_create.assert_not_called()
    assert db_session.query(Requests).count() == 0


def test_chat_cancel_at_justification_step_via_keyword(client, auth_headers, db_session):
    history = [
        {"role": "user", "content": "I'd like to create a Hardware request."},
        {"role": "assistant", "content": "How urgent is this?\n1. Low\n2. Medium\n3. High\n4. Urgent"},
        {"role": "user", "content": "4"},
        {"role": "assistant", "content": "Got it, urgent. Can you give a short justification?"},
    ]

    with patch.object(chatbot._client.messages, "create") as mock_create:
        response = client.post(
            "/chat",
            json={"message": "actually never mind", "history": history, "in_creation_flow": True},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == chatbot.CANCEL_REQUEST_REPLY
    assert body["show_quick_options"] is True
    mock_create.assert_not_called()
    assert db_session.query(Requests).count() == 0


def test_chat_cancel_at_duplicate_confirmation_step_via_button(client, auth_headers, db_session):
    history = [
        {"role": "user", "content": "The printer is broken"},
        {
            "role": "assistant",
            "content": "That looks similar to request #47 (Printer not working). Want to create a new one anyway?",
        },
    ]

    with patch.object(chatbot, "check_similar_requests") as mock_check:
        with patch.object(chatbot._client.messages, "create") as mock_create:
            response = client.post(
                "/chat",
                json={"message": "cancel", "history": history, "in_creation_flow": True},
                headers=auth_headers,
            )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == chatbot.CANCEL_REQUEST_REPLY
    assert body["show_quick_options"] is True
    mock_create.assert_not_called()
    mock_check.assert_not_called()
    assert db_session.query(Requests).count() == 0


def test_chat_cancel_variants_all_recognized(client, auth_headers, db_session):
    history = [
        {"role": "user", "content": "I'd like to create a Hardware request."},
        {"role": "assistant", "content": "How urgent is this?\n1. Low\n2. Medium\n3. High\n4. Urgent"},
    ]

    for phrase in ["cancel", "Cancel.", "STOP", "back", "start over", "nvm", "quit", "exit"]:
        with patch.object(chatbot._client.messages, "create") as mock_create:
            response = client.post(
                "/chat",
                json={"message": phrase, "history": history, "in_creation_flow": True},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["reply"] == chatbot.CANCEL_REQUEST_REPLY, f"failed for phrase: {phrase!r}"
        mock_create.assert_not_called()

    assert db_session.query(Requests).count() == 0


def test_chat_cancel_keyword_ignored_outside_creation_flow(client, auth_headers):
    # Without in_creation_flow set, a bare "cancel" or "stop" is just an
    # ordinary message and goes to the model like anything else.
    final = _text_response("Sure, what would you like help with?")

    with patch.object(chatbot._client.messages, "create", return_value=final) as mock_create:
        response = client.post(
            "/chat",
            json={"message": "cancel", "history": [], "in_creation_flow": False},
            headers=auth_headers,
        )

    assert response.status_code == 200
    sent_messages = mock_create.call_args.kwargs["messages"]
    assert sent_messages[-1]["content"] == "cancel"
    mock_create.assert_called_once()


def test_chat_cancel_keyword_does_not_false_positive_on_similar_wording(client, auth_headers, db_session):
    # "stop" is a cancel phrase on its own, but must not match as a substring
    # inside real request content — the check is whole-message, not "contains".
    tool_call = _tool_use_response(
        "create_request",
        {"request_type": "hardware", "description": "The printer stopped working, please help", "priority": "P1"},
    )
    final = _text_response("I've created your hardware request.")
    history = [
        {"role": "user", "content": "I'd like to create a Hardware request."},
        {"role": "assistant", "content": "What's the issue and how urgent is it?"},
    ]

    with patch.object(chatbot, "check_similar_requests", return_value=None):
        with patch.object(chatbot._client.messages, "create", side_effect=[tool_call, final]) as mock_create:
            response = client.post(
                "/chat",
                json={
                    "message": "The printer stopped working, please help. High priority.",
                    "history": history,
                    "in_creation_flow": True,
                },
                headers=auth_headers,
            )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] != chatbot.CANCEL_REQUEST_REPLY
    assert body["request_created"] is True
    # The message was sent through to the model as-is, not swallowed as a cancel.
    # (index len(history) is the freshly appended user turn — `messages` is
    # mutated in place across the tool-use loop, so later list entries aren't
    # stable to assert on by the time the response comes back.)
    first_call_messages = mock_create.call_args_list[0].kwargs["messages"]
    assert first_call_messages[len(history)]["content"] == "The printer stopped working, please help. High priority."
    created = db_session.query(Requests).filter(Requests.description == "The printer stopped working, please help").first()
    assert created is not None


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
