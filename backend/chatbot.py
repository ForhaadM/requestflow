import json
import logging
import os

import anthropic
from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import User, Requests, REQUEST_TYPES, PRIORITIES
from request_service import create_request_for_user, get_request_for_user
from duplicate_detection import check_similar_requests

load_dotenv()

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 1024
MAX_TOOL_ITERATIONS = 4

SYSTEM_PROMPT = (
    "You are Flowy Assistant, embedded in RequestFlow, an internal request management tool. "
    "You help the current user create requests and check on existing ones.\n\n"
    f"Valid request_type values: {', '.join(REQUEST_TYPES)}.\n\n"
    "Priority levels (never say the internal codes to the user, just use these names): "
    "Low (P3), Medium (P2), High (P1, the default), Urgent (P0).\n\n"
    "When the user describes something they need, pick the closest request_type yourself (no need to "
    "show a menu in that case).\n\n"
    "The moment you know both the request_type and a description of what the user needs, call the "
    "ask_urgency tool before calling create_request — do NOT hand-write the urgency question yourself, "
    "and do NOT call create_request with a default/assumed priority without asking first. The only "
    "exception is if the user already stated the urgency unprompted in their own words (e.g. \"this is "
    "urgent\" alongside their description) — in that case you already have what you need and can skip "
    "straight to create_request, still asking for a justification if it's Urgent/P0.\n\n"
    "If they pick option 4 / Urgent (priority Urgent = P0), you must also collect a short "
    "justification before calling create_request. For Low/Medium/High, no justification is needed. "
    "Don't ask for information you can reasonably infer. Keep replies short and conversational.\n\n"
    "If you know which request_type the user wants but they haven't described what they actually need "
    "yet — e.g. they picked a type from the menu, or named a category without describing the issue — "
    "call the request_type_selected tool with that request_type instead of asking \"what do you need\" "
    "in your own words; it shows category-specific examples deterministically.\n\n"
    "If you don't yet know which request_type the user wants at all — e.g. they said they want to "
    "create one without describing what they need, or they just agreed after you offered to create "
    "one for them — call the show_request_type_menu tool instead of asking in your own words.\n\n"
    "Never hand-write the type list or the \"what do you need\" prompt yourself in either of the above "
    "two cases; they must come from their respective tools every time, with no exceptions, so the menu "
    "and its examples are always shown and the user's next reply is parsed reliably.\n\n"
    "If the user asks what request types/categories exist or what they can submit purely out of "
    "curiosity (e.g. \"what can I submit\", \"what request types are there\") — not as the start of "
    "creating a request — call the list_request_types tool instead. Never hand-write this list either, "
    "it must come from the tool.\n\n"
    "create_request automatically checks for likely duplicates among the user's own open requests. "
    "If it returns duplicate_warning instead of created, do NOT call create_request again yet — tell "
    "the user which existing request(s) it resembles (id and description) and ask if they still want "
    "to create a new one. Only if they confirm, call create_request again with the same arguments plus "
    "confirmed_duplicate set to true."
)

TOOLS = [
    {
        "name": "create_request",
        "description": "Create a new request owned by the current user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "request_type": {"type": "string", "enum": list(REQUEST_TYPES)},
                "description": {"type": "string", "description": "Short description of what's needed."},
                "priority": {
                    "type": "string",
                    "enum": list(PRIORITIES),
                    "description": "P0=Urgent, P1=High, P2=Medium, P3=Low. Always the user's explicit "
                    "answer to the urgency question (via ask_urgency) or something they stated "
                    "unprompted — never assumed or defaulted silently.",
                },
                "urgency_justification": {
                    "type": "string",
                    "description": "Required if priority is P0 (Urgent).",
                },
                "confirmed_duplicate": {
                    "type": "boolean",
                    "description": "Set true only after the user has confirmed they still want to "
                    "create this request despite a previously reported duplicate_warning.",
                    "default": False,
                },
            },
            "required": ["request_type", "description", "priority"],
        },
    },
    {
        "name": "get_request_status",
        "description": "Look up a single request by its ID and return its status and details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "integer"},
            },
            "required": ["request_id"],
        },
    },
    {
        "name": "list_my_requests",
        "description": "List the current user's own requests (id, type, priority, status).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_request_types",
        "description": "Show the user a purely informational numbered list of request types they can "
        "submit — this does NOT start a request-creation flow. Call this whenever the user asks what "
        "request types/categories exist or what they can submit — do not write the list out yourself, "
        "it's rendered deterministically from this tool call.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "show_request_type_menu",
        "description": "Show the user the numbered menu of request types and start the guided creation "
        "flow — call this every time you need to ask which type of request they want (they haven't "
        "described what they need, or just agreed to create one) instead of asking in your own words. "
        "Do not write the list out yourself, it's rendered deterministically from this tool call.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "request_type_selected",
        "description": "Call this the moment you know which request_type the user wants but don't yet "
        "have a description of what they actually need — e.g. they picked a type from the menu, or "
        "named a category without describing the issue. Do not ask \"what do you need\" yourself in "
        "this situation; this tool shows category-specific examples deterministically.",
        "input_schema": {
            "type": "object",
            "properties": {"request_type": {"type": "string", "enum": list(REQUEST_TYPES)}},
            "required": ["request_type"],
        },
    },
    {
        "name": "ask_urgency",
        "description": "Call this the moment you know both the request_type and a description of what "
        "the user needs, before calling create_request — never call create_request with a "
        "default/assumed priority without asking this first. Skip only if the user already stated the "
        "urgency unprompted in their own words. Do not hand-write the urgency question yourself, it "
        "must come from this tool.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

# Shown to the user whenever the Anthropic API can't be reached at all
# (rate limit, out of credits, network error, 5xx/overloaded, etc.) so the
# widget degrades gracefully instead of hanging or crashing.
UNAVAILABLE_MESSAGE = (
    "The assistant is temporarily unavailable — please use the New Request form directly."
)

# Intent sent by the ChatWidget's "Create a new request" quick option. Handled
# entirely deterministically below (no Anthropic call) so the numbered list is
# generated straight from REQUEST_TYPES and can never drift or be hallucinated.
CREATE_REQUEST_MENU_INTENT = "create_request_menu"

# Name of the tool the model must call (instead of hand-writing the list) whenever
# a general question ("what can I submit?") wants to show the type list. Intercepted
# below so the reply is always exactly INFO_REQUEST_TYPES_REPLY — a purely
# informational listing, distinct in wording from CREATE_REQUEST_MENU_REPLY so the
# next turn's menu-selection check (below), which matches on exact text, does NOT
# treat a follow-up number as a request-type selection for this path.
LIST_REQUEST_TYPES_TOOL = "list_request_types"

# Name of the tool the model must call (instead of freely asking "what type of
# request...") whenever it needs to start the guided creation flow itself — e.g.
# the user agreed to create one after being offered, with no type described yet.
# Intercepted below so this always produces the exact same CREATE_REQUEST_MENU_REPLY
# text as the dedicated "Create a new request" button, regardless of which
# conversational path led here — the numbered list must never be skipped.
SHOW_REQUEST_TYPE_MENU_TOOL = "show_request_type_menu"

# Name of the tool the model must call (instead of freely asking "what do you
# need") the moment it knows the request_type but doesn't have a description
# yet — e.g. right after a menu selection, or the user named a category
# without describing the issue. Intercepted below so the category examples
# are always shown, regardless of which path established the type.
REQUEST_TYPE_SELECTED_TOOL = "request_type_selected"

# Name of the tool the model must call (instead of hand-writing the urgency
# question, or worse, silently defaulting create_request's priority to P1)
# the moment it has both a request_type and a description. Intercepted below
# so the question is never skipped — closes the gap where the model could
# take the tool schema's default priority as a shortcut to create the request
# without ever asking the user how urgent it is.
ASK_URGENCY_TOOL = "ask_urgency"


def _pretty_type_label(request_type: str) -> str:
    return request_type.replace("-", " ").title()


_TYPE_MENU_LINES = "\n".join(
    f"{i}. {_pretty_type_label(t)}" for i, t in enumerate(REQUEST_TYPES, start=1)
)
CREATE_REQUEST_MENU_REPLY = (
    "Sure, what type of request do you want to create?\n\n" + _TYPE_MENU_LINES
)

# Mirrors the `examples` lists in frontend/src/lib/requestTypes.js (the New
# Request form's per-type tooltip) so the chatbot and the form describe each
# category the same way. Kept in sync by hand since the two live in separate
# languages/runtimes with no shared source.
_CATEGORY_EXAMPLES: dict[str, list[str]] = {
    "hardware": ["Laptop or monitor request", "Broken keyboard or mouse", "Docking station needed"],
    "software": ["New software license", "App installation request", "Software upgrade"],
    "access-request": ["VPN access", "Shared drive/folder permissions", "System or tool access"],
    "account-password": ["Password reset", "Account locked out", "MFA reset"],
    "bug-report": ["App crashing", "Broken feature", "Error message on a page"],
    "network": ["Wi-Fi not working", "Slow internet", "VPN connection issues"],
    "onboarding-offboarding": ["New hire equipment setup", "Account deprovisioning", "Employee departure checklist"],
    "facilities": ["Broken office equipment", "Badge/access card issue", "Conference room AV problem"],
    "other": ["Anything that doesn't fit the categories above"],
}


def _type_selected_reply(request_type: str) -> str:
    label = _pretty_type_label(request_type)
    examples = "\n".join(f"- {example}" for example in _CATEGORY_EXAMPLES[request_type])
    return f"Got it — a {label} request. This usually covers things like:\n{examples}\n\nWhat do you need?"


ASK_URGENCY_REPLY = "How urgent is this?\n1. Low\n2. Medium\n3. High\n4. Urgent (requires a justification)"

# Purely informational — answers "what can I submit?" without starting a creation
# flow, so it deliberately does not end on a question expecting a numbered reply.
INFO_REQUEST_TYPES_REPLY = (
    "These are the types of requests you can make:\n\n" + _TYPE_MENU_LINES +
    "\n\nLet me know if you'd like to create a new request, check on an existing one, "
    "or ask something else."
)

CANCEL_REQUEST_REPLY = "No problem, I've cancelled that. What would you like to do instead?"

# Whole-message cancel-intent phrases (matched after strip/lowercase/trailing
# punctuation removal — never as a substring), so a real request description
# like "the printer stopped working, please help" can't match "stop". Only
# checked while a guided creation flow is actually in progress (see
# `in_creation_flow` in run_chat), so an unrelated message elsewhere in the
# conversation is never at risk of being misread as a cancellation.
_CANCEL_PHRASES = {
    "cancel", "cancel it", "cancel this", "cancel that", "cancel please", "please cancel",
    "nevermind", "never mind", "nvm", "actually nevermind", "actually never mind",
    "back", "go back", "start over", "restart", "stop", "quit", "exit",
}


def _is_cancel_intent(text: str) -> bool:
    normalized = text.strip().lower().rstrip(".!?")
    return normalized in _CANCEL_PHRASES


def _parse_request_type_selection(text: str) -> str | None:
    """Resolve a user's reply to the type menu — either a number (1-based
    index into REQUEST_TYPES) or the type's code/pretty label, case- and
    separator-insensitive — into a REQUEST_TYPES value. Returns None if the
    reply doesn't match anything, so the caller can fall back to the normal
    LLM path instead of guessing."""
    normalized = text.strip()
    if normalized.endswith(".") and normalized[:-1].isdigit():
        normalized = normalized[:-1]
    if normalized.isdigit():
        index = int(normalized)
        if 1 <= index <= len(REQUEST_TYPES):
            return REQUEST_TYPES[index - 1]
        return None

    normalized = normalized.lower().replace("-", " ").strip()
    for request_type in REQUEST_TYPES:
        if normalized == request_type.replace("-", " ") or normalized == _pretty_type_label(request_type).lower():
            return request_type
    return None


def _serialize_request(req: Requests) -> dict:
    return {
        "request_id": req.request_id,
        "request_type": req.request_type,
        "description": req.description,
        "priority": req.priority,
        "status": req.status,
        "urgency_justification": req.urgency_justification,
        "created_at": req.created_at.isoformat() if req.created_at else None,
    }


def _run_tool(name: str, tool_input: dict, db: Session, current_user: User) -> dict:
    """Execute one tool call scoped to current_user. Never trusts a user/requester
    ID from the model — request ownership always comes from current_user."""
    if name == "create_request":
        request_type = tool_input.get("request_type")
        if request_type not in REQUEST_TYPES:
            return {"error": f"'{request_type}' is not a valid request_type."}
        # No fallback default here on purpose: priority must be the user's actual
        # answer to ask_urgency (or something they stated unprompted), never a
        # silent assumption — that silent-default path is exactly what let the
        # model skip asking urgency and create requests at P1 without asking.
        priority = tool_input.get("priority")
        if priority not in PRIORITIES:
            return {"error": f"'{priority}' is not a valid priority — ask the user how urgent this is."}

        description = tool_input.get("description")
        if not tool_input.get("confirmed_duplicate"):
            matches = check_similar_requests(db, current_user, request_type, description)
            if matches:
                return {"duplicate_warning": {"matches": matches}}

        try:
            new_request = create_request_for_user(
                db,
                current_user,
                request_type=request_type,
                description=description,
                priority=priority,
                urgency_justification=tool_input.get("urgency_justification"),
            )
        except HTTPException as exc:
            return {"error": exc.detail}
        return {"created": _serialize_request(new_request)}

    if name == "get_request_status":
        try:
            req = get_request_for_user(db, current_user, tool_input.get("request_id"))
        except HTTPException as exc:
            return {"error": exc.detail}
        return {"request": _serialize_request(req)}

    if name == "list_my_requests":
        requests = (
            db.query(Requests)
            .filter(Requests.requester_reference == current_user.user_id)
            .order_by(Requests.created_at.desc())
            .all()
        )
        return {"requests": [_serialize_request(r) for r in requests]}

    return {"error": f"Unknown tool '{name}'."}


def run_chat(
    message: str,
    history: list[dict],
    db: Session,
    current_user: User,
    intent: str | None = None,
    in_creation_flow: bool = False,
) -> tuple[str, bool, bool, bool]:
    """Send a user message through the Claude tool-use loop and return
    (assistant's final text reply, whether a request was actually created
    during this turn, whether the client should re-show the quick-option
    buttons, whether the client should now consider itself mid guided-creation-flow).
    `history` is a list of {role, content} text turns supplied by the client
    (v1: client-side conversation state).

    The `request_created` flag lets the client know to refresh any
    request lists it has on screen (My Requests, Review Queue, ...) —
    without it, a request created through this always-mounted widget would
    sit unseen until the user happened to navigate/remount that page.

    The `show_quick_options` flag is set after the purely informational
    "what can I submit?" listing (INFO_REQUEST_TYPES_REPLY), and after a
    cancellation, since neither leads anywhere on its own — the client
    should present the same Create a new request / Check on a request /
    What can I submit? buttons it shows at the start of a conversation,
    rather than leaving the user with only a text box.

    `intent`, when set by the client (e.g. the "Create a new request" quick
    option), triggers a deterministic, non-LLM reply instead of a model call —
    see CREATE_REQUEST_MENU_INTENT.

    `in_creation_flow` (input) is set by the client for the duration of the
    guided creation flow and gates the deterministic cancel-keyword check
    below — scoping that check to only fire while a flow is actually active
    (rather than on every message) is what keeps ordinary request content
    (e.g. "the printer stopped working") from ever being misread as "stop".
    The returned `in_creation_flow` (this function is the source of truth,
    not the client) is resolved by `resolve_flow` on every
    return path below: it becomes True the moment CREATE_REQUEST_MENU_REPLY
    is shown — whether from the dedicated button, or the model calling
    SHOW_REQUEST_TYPE_MENU_TOOL because the user agreed to create a request
    without describing one yet — and False once a request is actually
    created, the flow is cancelled, or it dead-ends into the informational
    listing; otherwise it carries the input value forward, since the
    urgency/justification/duplicate-confirm steps are free-form model
    conversation with no explicit server-side state of their own. Nothing is
    ever persisted mid-flow (create_request only runs after the user reaches
    and confirms the final step), so cancelling never requires cleaning up
    partial data — there isn't any to clean up.

    If the Anthropic API fails for any reason (rate limit, out of credits,
    network error, ...), catches it and returns a friendly message instead
    of raising, so the chat widget degrades gracefully instead of hanging.
    """

    def resolve_flow(reply: str, request_created: bool, still_in_flow: bool) -> bool:
        if request_created:
            return False
        if reply == CREATE_REQUEST_MENU_REPLY:
            return True
        return still_in_flow

    if intent == CREATE_REQUEST_MENU_INTENT:
        return CREATE_REQUEST_MENU_REPLY, False, False, True

    menu_is_active = bool(
        history and history[-1].get("role") == "assistant" and history[-1].get("content") == CREATE_REQUEST_MENU_REPLY
    )
    if (in_creation_flow or menu_is_active) and _is_cancel_intent(message):
        return CANCEL_REQUEST_REPLY, False, True, False

    # If the assistant's last turn was the type menu, try to resolve this
    # reply as a selection ourselves (number or type name) rather than
    # leaving the parsing to the model — deterministic and free. No model
    # call needed at all here: we already know the type, so we can go
    # straight to the deterministic category-examples reply (the same one
    # REQUEST_TYPE_SELECTED_TOOL produces below for the other entry point),
    # guaranteeing the examples are shown every time, not just when the
    # model remembers to ask for them itself.
    if menu_is_active:
        selected_type = _parse_request_type_selection(message)
        if selected_type:
            return _type_selected_reply(selected_type), False, False, True

    outgoing_message = message
    messages = [{"role": h["role"], "content": h["content"]} for h in history]
    messages.append({"role": "user", "content": outgoing_message})

    request_created = False

    try:
        response = _client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages,
        )
    except anthropic.APIError as exc:
        logger.warning("Anthropic API call failed: %s", exc)
        return UNAVAILABLE_MESSAGE, request_created, False, in_creation_flow

    for _ in range(MAX_TOOL_ITERATIONS):
        if response.stop_reason != "tool_use":
            break

        # Short-circuit these two here rather than executing/returning their result
        # to the model: we want the exact deterministic reply text, not whatever the
        # model would phrase around a tool result, so the numbered list can never be
        # skipped or drift, and next turn's menu-selection check (which matches
        # CREATE_REQUEST_MENU_REPLY only) correctly recognizes it regardless of
        # which conversational path led here.
        if any(block.type == "tool_use" and block.name == LIST_REQUEST_TYPES_TOOL for block in response.content):
            return INFO_REQUEST_TYPES_REPLY, request_created, True, False
        if any(block.type == "tool_use" and block.name == SHOW_REQUEST_TYPE_MENU_TOOL for block in response.content):
            return CREATE_REQUEST_MENU_REPLY, request_created, False, True
        type_selected_block = next(
            (b for b in response.content if b.type == "tool_use" and b.name == REQUEST_TYPE_SELECTED_TOOL),
            None,
        )
        if type_selected_block is not None:
            selected_type = type_selected_block.input.get("request_type")
            if selected_type in REQUEST_TYPES:
                return _type_selected_reply(selected_type), request_created, False, True
        if any(block.type == "tool_use" and block.name == ASK_URGENCY_TOOL for block in response.content):
            return ASK_URGENCY_REPLY, request_created, False, True

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = _run_tool(block.name, block.input, db, current_user)
            if block.name == "create_request" and "created" in result:
                request_created = True
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                    "is_error": "error" in result,
                }
            )
        messages.append({"role": "user", "content": tool_results})

        try:
            response = _client.messages.create(
                model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages,
            )
        except anthropic.APIError as exc:
            logger.warning("Anthropic API call failed mid-conversation: %s", exc)
            # The tool call itself (and any request it created) already
            # happened before this second API call failed, so still report it.
            return UNAVAILABLE_MESSAGE, request_created, False, resolve_flow("", request_created, in_creation_flow)

    reply = next((b.text for b in response.content if b.type == "text"), "")
    reply = reply or "I wasn't able to come up with a response — could you rephrase that?"
    return (
        reply,
        request_created,
        False,
        resolve_flow(reply, request_created, in_creation_flow),
    )
