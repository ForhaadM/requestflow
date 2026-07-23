from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from database import Base
from typing import Optional

# User, Request, Review classes will go here

# Single source of truth for the Requests CheckConstraints below — also used
# by the chatbot (chatbot.py) so its tool schemas/system prompt can't drift
# from what the database will actually accept.
REQUEST_TYPES = (
    "hardware", "software", "access-request", "account-password",
    "bug-report", "network", "onboarding-offboarding", "facilities", "other",
)
PRIORITIES = ("P0", "P1", "P2", "P3")

class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(50))

    __table_args__ = (
        CheckConstraint("role IN ('requester', 'reviewer', 'admin')"),
    )

class Requests(Base):
    __tablename__ = "requests"

    request_id: Mapped[int] = mapped_column(primary_key=True)
    requester_reference: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    request_type: Mapped[str] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default = "P1")
    urgency_justification: Mapped[Optional[str]] = mapped_column(Text)
    # Indexed: filtered via .in_()/== in search_requests, list_my_requests,
    # get_requests_summary, and analytics.py's terminal/open-status queries.
    status: Mapped[str] = mapped_column(String(20), default = "open", index=True)
    claimed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.user_id"))
    # timezone=True (Postgres timestamptz): without it, the column silently
    # truncates func.now()'s timezone-aware UTC value to a naive one on
    # write, and the driver hands back a naive datetime on read. Pydantic
    # then serializes that with no UTC offset/'Z' suffix, so the browser's
    # `new Date(...)` — per the JS date-time parsing spec — treats it as
    # local time instead of UTC, shifting every displayed timestamp by
    # whatever the viewer's UTC offset happens to be.
    # Indexed: default ORDER BY for search_requests/list_my_requests, and
    # analytics.py's date-range filters (volume trends, spikes).
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
    CheckConstraint(
        "request_type IN (" + ", ".join(f"'{t}'" for t in REQUEST_TYPES) + ")"
    ),
    CheckConstraint("priority IN (" + ", ".join(f"'{p}'" for p in PRIORITIES) + ")"),
    # "resolved" was never wired up on any code path (StatusEnum in main.py
    # only allows open/in-progress/closed; review decisions only ever set
    # approved/rejected) — dropped rather than left as a reachable-looking
    # but dead status. See alembic/versions for the migration that removes
    # it from the DB constraint too.
    # "cancelled" is set only via PATCH /requests/{id}/cancel, by the owning
    # requester, and only while the request hasn't been decided yet (see
    # cancel_request_for_user in request_service.py).
    CheckConstraint(
        "status IN ('open', 'in-progress', 'closed', 'approved', 'rejected', 'cancelled')",
        name="requests_status_check",
    ),
)

class Reviews(Base):
    __tablename__ = "reviews"

    review_id: Mapped[int] = mapped_column(primary_key=True)
    request_reference: Mapped[int] = mapped_column(ForeignKey("requests.request_id"))
    reviewer_reference: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    decision: Mapped[str] = mapped_column(String(50))
    comment_text: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("decision IN ('APPROVED', 'NOT APPROVED')"),

    )

class Comments(Base):
    __tablename__ = "comments"

    comment_id: Mapped[int] = mapped_column(primary_key=True)
    request_reference: Mapped[int] = mapped_column(ForeignKey("requests.request_id"))
    commenter_reference: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    comment_text: Mapped[str] = mapped_column(Text)
    # timezone=True (Postgres timestamptz): without it, the column silently
    # truncates func.now()'s timezone-aware UTC value to a naive one on
    # write, and the driver hands back a naive datetime on read. Pydantic
    # then serializes that with no UTC offset/'Z' suffix, so the browser's
    # `new Date(...)` — per the JS date-time parsing spec — treats it as
    # local time instead of UTC, shifting every displayed timestamp by
    # whatever the viewer's UTC offset happens to be.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())