from fastapi import HTTPException
from sqlalchemy import or_
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


def search_requests(
    db: Session,
    search: str | None = None,
    statuses: list[str] | None = None,
    priorities: list[str] | None = None,
    request_types: list[str] | None = None,
):
    """Build the reviewer/admin "all requests" query with optional search and
    filters applied in SQL, rather than fetching everything and filtering in
    Python — so this scales the same way whether the caller adds LIMIT/OFFSET
    or a cursor on top later.

    `search` matches request ID (exact, only when the term is purely numeric),
    requester name, requester email, or description (substring, case-insensitive).
    `statuses`/`priorities`/`request_types` are separate, combinable filters —
    each an OR across its own list, ANDed against everything else.
    """
    query = db.query(Requests).join(User, Requests.requester_reference == User.user_id)

    term = (search or "").strip()
    if term:
        conditions = [
            User.name.ilike(f"%{term}%"),
            User.email.ilike(f"%{term}%"),
            Requests.description.ilike(f"%{term}%"),
        ]
        if term.isdigit():
            conditions.append(Requests.request_id == int(term))
        query = query.filter(or_(*conditions))

    if statuses:
        query = query.filter(Requests.status.in_(statuses))
    if priorities:
        query = query.filter(Requests.priority.in_(priorities))
    if request_types:
        query = query.filter(Requests.request_type.in_(request_types))

    return query.order_by(Requests.created_at.desc()).all()


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
    """Add a comment to a request: the owning requester, an admin (matching
    their broader access elsewhere, e.g. unclaim_request), or the reviewer
    currently holding the claim (claimed_by, not request status — so they
    keep access after the ticket is approved/rejected/closed to leave a
    follow-up, but lose it if they unclaim)."""
    existing_request = db.query(Requests).filter(Requests.request_id == request_id).first()
    if not existing_request:
        raise HTTPException(status_code=404, detail="Request not found.")

    is_owner = current_user.user_id == existing_request.requester_reference
    is_admin = current_user.role == "admin"
    is_claiming_reviewer = (
        current_user.role == "reviewer" and current_user.user_id == existing_request.claimed_by
    )
    if not (is_owner or is_admin or is_claiming_reviewer):
        raise HTTPException(status_code=403, detail="Not authorized to comment on this request.")
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
    # Transient, not persisted — the author is always current_user here, so
    # no extra query is needed to know their name (see list_comments_for_request
    # for the multi-author case, which does need one).
    new_comment.commenter_name = current_user.name
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

    comments = (
        db.query(Comments)
        .filter(Comments.request_reference == request_id)
        .order_by(Comments.created_at)
        .all()
    )

    # The owning requester has no directory access (GET /users is
    # reviewer/admin-only), so the commenter's name is resolved here and
    # sent in-band rather than requiring the frontend to look it up.
    if comments:
        commenter_ids = {c.commenter_reference for c in comments}
        names_by_id = {
            u.user_id: u.name
            for u in db.query(User).filter(User.user_id.in_(commenter_ids)).all()
        }
        for c in comments:
            c.commenter_name = names_by_id.get(c.commenter_reference, "Unknown user")

    return comments
