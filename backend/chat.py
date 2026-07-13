from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import User
from chatbot import run_chat
from rate_limit import enforce_rate_limit

router = APIRouter()

# Bounds cost/abuse — the client resends the full history on every turn, so
# an unbounded message/history size is a per-request Anthropic API cost the
# client fully controls.
MAX_MESSAGE_LENGTH = 2000
MAX_HISTORY_TURNS = 40


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str = Field(max_length=MAX_MESSAGE_LENGTH)


class ChatRequest(BaseModel):
    message: str = Field(max_length=MAX_MESSAGE_LENGTH)
    history: list[ChatMessage] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS)
    # Set by specific UI triggers (e.g. the "Create a new request" quick
    # option) to request a deterministic, non-LLM reply — see chatbot.py.
    intent: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    history: list[ChatMessage]
    # True when this turn actually created a request, so the client knows to
    # refresh any request lists it has on screen (see chatbot.run_chat).
    request_created: bool = False


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enforce_rate_limit(f"chat:{current_user.user_id}", max_requests=20, window_seconds=60)
    reply, request_created = run_chat(
        request.message,
        [h.model_dump() for h in request.history],
        db,
        current_user,
        intent=request.intent,
    )
    updated_history = request.history + [
        ChatMessage(role="user", content=request.message),
        ChatMessage(role="assistant", content=reply),
    ]
    return ChatResponse(reply=reply, history=updated_history, request_created=request_created)
