import json
import logging
import os

import anthropic
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from models import User, Requests

load_dotenv()

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 512

# How many of the user's own recent open/in-progress requests to consider.
# Bounded to keep the prompt (and cost) tiny — a user realistically has a
# handful of active requests at once, not dozens.
CANDIDATE_LIMIT = 15

# "Not yet resolved" from the requester's perspective — claimed-but-undecided
# (in-progress) is still active, so a new duplicate submission is worth
# catching against it too.
ACTIVE_STATUSES = ("open", "in-progress")

SYSTEM_PROMPT = (
    "You compare a new support/IT request against a list of the same user's existing open "
    "requests and identify likely duplicates — requests describing the same underlying problem "
    "or need, even if worded differently (e.g. \"laptop won't turn on\" and \"computer not "
    "powering on\" are duplicates). Only flag genuine duplicates, not merely related requests "
    "(e.g. two different software license requests are not duplicates of each other)."
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "integer"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["request_id", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["matches"],
    "additionalProperties": False,
}

# "low" confidence matches are too noisy to surface as a warning.
REPORTABLE_CONFIDENCE = {"high", "medium"}


def _serialize_match(req: Requests, confidence: str) -> dict:
    return {
        "request_id": req.request_id,
        "request_type": req.request_type,
        "description": req.description,
        "priority": req.priority,
        "status": req.status,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "confidence": confidence,
    }


def check_similar_requests(
    db: Session, current_user: User, request_type: str, description: str
) -> list[dict]:
    """Return the user's own active requests that look like duplicates of the
    given (request_type, description), most-confident first.

    Scoped to the current user's own open/in-progress requests only — never
    compares across users. Makes at most one small Claude Haiku call, and
    only when the user actually has candidates to compare against. Fails
    open (returns no matches) on any Anthropic API error, so a duplicate
    check can never block request creation.
    """
    if not description or not description.strip():
        return []

    candidates = (
        db.query(Requests)
        .filter(
            Requests.requester_reference == current_user.user_id,
            Requests.status.in_(ACTIVE_STATUSES),
        )
        .order_by(Requests.created_at.desc())
        .limit(CANDIDATE_LIMIT)
        .all()
    )
    if not candidates:
        return []

    candidates_by_id = {c.request_id: c for c in candidates}
    candidate_lines = "\n".join(
        f"- id={c.request_id}, type={c.request_type}: {c.description}" for c in candidates
    )
    user_prompt = (
        f"New request — type={request_type}: {description}\n\n"
        f"Existing open requests from the same user:\n{candidate_lines}"
    )

    try:
        response = _client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
        )
    except anthropic.APIError as exc:
        logger.warning("Duplicate-check API call failed, skipping check: %s", exc)
        return []

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        return []

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Duplicate-check returned unparseable output: %r", text)
        return []

    matches = []
    for m in parsed.get("matches", []):
        req = candidates_by_id.get(m.get("request_id"))
        if req is None or m.get("confidence") not in REPORTABLE_CONFIDENCE:
            continue
        matches.append(_serialize_match(req, m["confidence"]))

    matches.sort(key=lambda m: 0 if m["confidence"] == "high" else 1)
    return matches
