from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from database import Base
from typing import Optional

# User, Request, Review classes will go here

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
    status: Mapped[str] = mapped_column(String(20), default = "open")
    claimed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
    CheckConstraint(
        "request_type IN ('hardware', 'software', 'access-request', 'account-password', "
        "'bug-report', 'network', 'onboarding-offboarding', 'facilities', 'other')"
    ),
    CheckConstraint("priority IN ('P0', 'P1', 'P2', 'P3')"),
    CheckConstraint("status IN ('open', 'in-progress', 'resolved', 'closed', 'approved', 'rejected')"),
)

class Reviews(Base):
    __tablename__ = "reviews"

    review_id: Mapped[int] = mapped_column(primary_key=True)
    request_reference: Mapped[int] = mapped_column(ForeignKey("requests.request_id"))
    reviewer_reference: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    decision: Mapped[str] = mapped_column(String(50))
    comment_text: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint("decision IN ('APPROVED', 'NOT APPROVED')"),

    )