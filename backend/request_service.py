from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import User, Requests

# Request types that represent an issue being fixed rather than something being
# granted, so an "approval" means work was done and should say how.
# (Mirrors main.py's ISSUE_REQUEST_TYPES — kept here since create_request_for_user
# doesn't need it, but get_request_for_user callers may in the future.)


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


def get_request_for_user(db: Session, current_user: User, request_id: int) -> Requests:
    """Fetch a request by ID, enforcing the same owner-or-admin rule as GET /requests/{id}."""
    existing_request = db.query(Requests).filter(Requests.request_id == request_id).first()
    if not existing_request:
        raise HTTPException(status_code=404, detail="Request not found.")
    if current_user.role == "admin" or current_user.user_id == existing_request.requester_reference:
        return existing_request
    raise HTTPException(status_code=403, detail="Not Authorized to see request.")
