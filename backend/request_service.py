from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import User, Requests, Reviews, Comments

# Request types that represent an issue being fixed rather than something being
# granted, so an "approval" means work was done and should say how.
ISSUE_REQUEST_TYPES = {"bug-report", "network", "facilities"}


def create_request_for_user(
    db: Session,
    current_user: User,
    request_type: str,
    description: str | None,
    priority: str,
    urgency_justification: str | None = None,
) -> Requests:
    """Validate and create a request owned by current_user.

    Shared by POST /requests and the chatbot's create_request tool so both
    paths enforce identical rules.
    """
    if not (description and description.strip()):
        raise HTTPException(status_code=400, detail="A description is required.")

    if priority == "P0" and not (urgency_justification and urgency_justification.strip()):
        raise HTTPException(
            status_code=400,
            detail="A justification is required for Urgent priority requests.",
        )

    new_request = Requests(
        requester_reference=current_user.user_id,
        request_type=request_type,
        description=description,
        priority=priority,
        urgency_justification=urgency_justification,
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return new_request


def cancel_request_for_user(db: Session, current_user: User, request_id: int) -> Requests:
    """Let the owning requester withdraw a request they no longer need.

    Only allowed while it's still unclaimed ("open") — once it's in-progress
    a reviewer is actively working it, and once it's been decided, cancelling
    it would retroactively undo a decision, which is what the admin override
    flow (create_review_for_user's is_override path) is for instead.
    """
    existing_request = (
        db.query(Requests).filter(Requests.request_id == request_id).with_for_update().first()
    )
    if not existing_request:
        raise HTTPException(status_code=404, detail="Request not found.")
    if current_user.user_id != existing_request.requester_reference:
        raise HTTPException(status_code=403, detail="You can only cancel your own requests.")
    if existing_request.status != "open":
        raise HTTPException(
            status_code=400,
            detail="Only open requests can be cancelled — an in-progress request is already being worked on.",
        )

    existing_request.status = "cancelled"
    db.commit()
    db.refresh(existing_request)
    return existing_request


def get_request_for_user(db: Session, current_user: User, request_id: int) -> Requests:
    """Fetch a request by ID, enforcing the same owner-or-admin rule as GET /requests/{id}."""
    existing_request = db.query(Requests).filter(Requests.request_id == request_id).first()
    if not existing_request:
        raise HTTPException(status_code=404, detail="Request not found.")
    if current_user.role == "admin" or current_user.user_id == existing_request.requester_reference:
        return existing_request
    raise HTTPException(status_code=403, detail="Not Authorized to see request.")


def create_review_for_user(
    db: Session,
    current_user: User,
    request_reference: int,
    decision: str,
    comment_text: str | None,
) -> Reviews:
    """Validate and create a review decision, enforcing claim/override rules.

    The single place POST /reviews' business rules live, so a future caller
    (e.g. a bulk-review endpoint) can reuse them instead of re-implementing
    the override/comment-required logic in a route handler.
    """
    if current_user.role not in ("reviewer", "admin"):
        raise HTTPException(status_code=403, detail="Only reviewers or admins can review requests.")

    # Lock the row: two conflicting decisions racing in at once (e.g. a
    # reviewer and an admin override) should be resolved one-at-a-time
    # against a consistent view of the request's current status.
    existing_request = (
        db.query(Requests).filter(Requests.request_id == request_reference).with_for_update().first()
    )
    if not existing_request:
        raise HTTPException(status_code=404, detail="Request not found.")

    # A request already sitting at "approved" or "rejected" was previously
    # decided; submitting another review on it overrides that decision
    # (in either direction) rather than being a first-time decision.
    is_override = existing_request.status in ("approved", "rejected")

    if is_override:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admins can override a previous decision.")
    else:
        if existing_request.status != "in-progress":
            raise HTTPException(status_code=400, detail="This request must be claimed before it can be reviewed.")
        if current_user.role == "reviewer" and existing_request.claimed_by != current_user.user_id:
            raise HTTPException(status_code=403, detail="Only the reviewer who claimed this request can submit a decision.")

    # Issue-style requests (bugs, network problems, facilities issues) need a
    # written explanation of how they were fixed, not just a rubber-stamp approval.
    requires_resolution_notes = existing_request.request_type in ISSUE_REQUEST_TYPES

    comment_required = (
        decision == "NOT APPROVED"
        or is_override
        or (decision == "APPROVED" and requires_resolution_notes)
    )

    if comment_required and not comment_text:
        if is_override:
            detail = "A comment is required when overriding a previous decision."
        elif decision == "APPROVED":
            detail = "A comment describing how this was resolved is required."
        else:
            detail = "A comment is required when rejecting a request."
        raise HTTPException(status_code=400, detail=detail)

    new_review = Reviews(
        request_reference=request_reference,
        reviewer_reference=current_user.user_id,
        decision=decision,
        comment_text=comment_text,
    )
    db.add(new_review)

    existing_request.status = "approved" if decision == "APPROVED" else "rejected"

    db.commit()
    db.refresh(new_review)
    return new_review


def create_comment_for_request(db: Session, current_user: User, request_id: int, comment_text: str) -> Comments:
    """Add a comment to a request. Only the request's own requester can add
    one — a requester can only comment on their own requests, per the brief."""
    existing_request = db.query(Requests).filter(Requests.request_id == request_id).first()
    if not existing_request:
        raise HTTPException(status_code=404, detail="Request not found.")
    if current_user.user_id != existing_request.requester_reference:
        raise HTTPException(status_code=403, detail="You can only comment on your own requests.")
    if existing_request.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot comment on a cancelled request.")

    new_comment = Comments(
        request_reference=request_id,
        commenter_reference=current_user.user_id,
        comment_text=comment_text,
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment


def list_comments_for_request(db: Session, current_user: User, request_id: int) -> list[Comments]:
    """Readable by the owning requester, any reviewer, or an admin — mirrors
    the same visibility reviewers/admins already have over the request itself
    via GET /requests, since they need this context while working a ticket."""
    existing_request = db.query(Requests).filter(Requests.request_id == request_id).first()
    if not existing_request:
        raise HTTPException(status_code=404, detail="Request not found.")

    is_owner = current_user.user_id == existing_request.requester_reference
    if not (is_owner or current_user.role in ("reviewer", "admin")):
        raise HTTPException(status_code=403, detail="Not authorized to see comments on this request.")

    return (
        db.query(Comments)
        .filter(Comments.request_reference == request_id)
        .order_by(Comments.created_at)
        .all()
    )
