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
    "You are the RequestFlow assistant, embedded in an internal request management tool. "
    "You help the current user create requests and check on existing ones.\n\n"
    f"Valid request_type values: {', '.join(REQUEST_TYPES)}.\n\n"
    "Priority levels (never say the internal codes to the user, just use these names): "
    "Low (P3), Medium (P2), High (P1, the default), Urgent (P0).\n\n"
    "When the user describes something they need, pick the closest request_type, then ask how "
    "urgent it is using exactly this format:\n"
    "How urgent is this?\n1. Low\n2. Medium\n3. High\n4. Urgent (requires a justification)\n\n"
    "If they pick option 4 / Urgent (priority Urgent = P0), you must also collect a short "
    "justification before calling create_request. For Low/Medium/High, no justification is needed. "
    "Don't ask for information you can reasonably infer. Keep replies short and conversational.\n\n"
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
                    "default": "P1",
                    "description": "P0=Urgent, P1=High (default), P2=Medium, P3=Low.",
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
            "required": ["request_type", "description"],
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
]

# Shown to the user whenever the Anthropic API can't be reached at all
# (rate limit, out of credits, network error, 5xx/overloaded, etc.) so the
# widget degrades gracefully instead of hanging or crashing.
UNAVAILABLE_MESSAGE = (
    "The assistant is temporarily unavailable — please use the New Request form directly."
)


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
        priority = tool_input.get("priority", "P1")
        if priority not in PRIORITIES:
            return {"error": f"'{priority}' is not a valid priority."}

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


def run_chat(message: str, history: list[dict], db: Session, current_user: User) -> str:
    """Send a user message through the Claude tool-use loop and return the
    assistant's final text reply. `history` is a list of {role, content} text
    turns supplied by the client (v1: client-side conversation state).

    If the Anthropic API fails for any reason (rate limit, out of credits,
    network error, ...), catches it and returns a friendly message instead
    of raising, so the chat widget degrades gracefully instead of hanging.
    """
    messages = [{"role": h["role"], "content": h["content"]} for h in history]
    messages.append({"role": "user", "content": message})

    try:
        response = _client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages,
        )
    except anthropic.APIError as exc:
        logger.warning("Anthropic API call failed: %s", exc)
        return UNAVAILABLE_MESSAGE

    for _ in range(MAX_TOOL_ITERATIONS):
        if response.stop_reason != "tool_use":
            break

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = _run_tool(block.name, block.input, db, current_user)
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
            return UNAVAILABLE_MESSAGE

    reply = next((b.text for b in response.content if b.type == "text"), "")
    return reply or "I wasn't able to come up with a response — could you rephrase that?"
