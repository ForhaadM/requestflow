import os
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from database import engine, get_db
from models import User, Requests, Reviews, REQUEST_TYPES, PRIORITIES
from typing import Optional
from enum import Enum
from auth import hash_password, verify_password, create_access_token, get_current_user
from request_service import create_request_for_user, get_request_for_user, create_review_for_user
from chat import router as chat_router
from duplicate_detection import check_similar_requests
from analytics import get_admin_analytics
from rate_limit import enforce_rate_limit

app = FastAPI()

# Comma-separated list of allowed frontend origins, e.g.:
#   ALLOWED_ORIGINS=https://d111111abcdef8.cloudfront.net,https://requestflow.example.com
# Defaults to the local Vite dev server so nothing changes for local dev.
_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
allow_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    name: str
    email: str
    role: str


@app.get("/users/me", response_model=UserPublic)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/users", response_model=list[UserPublic])
def get_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Full directory (names/emails/roles) is only needed by reviewer/admin
    # screens to label requesters and claimants — regular requesters use
    # GET /users/me instead, so this doesn't need to be world-readable.
    if current_user.role not in ["reviewer", "admin"]:
        raise HTTPException(status_code=403, detail="Only reviewers or admins can list all users.")
    return db.query(User).order_by(User.user_id).all()

@app.get("/requests")
def get_requests(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    if current_user.role not in ["admin", "reviewer"]:
        raise HTTPException(status_code=403,detail="Only admins or reviewers can see all requests.")
    return db.query(Requests).order_by(Requests.created_at.desc()).all() # Show me all requests in the system (Useful for admin/reviewer)


@app.get("/reviews")
def get_reviews(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == "admin":
        return db.query(Reviews).order_by(Reviews.reviewed_at).all()
    elif current_user.role == "reviewer":
        return db.query(Reviews).filter(Reviews.reviewer_reference == current_user.user_id).order_by(Reviews.reviewed_at).all()
    else:
        return []

@app.get("/requests/me")
def my_requests(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Requests).filter(Requests.requester_reference == current_user.user_id).order_by(Requests.created_at.desc()).all()

@app.get("/requests/{request_id}")
def get_request(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_request_for_user(db, current_user, request_id)

@app.get("/requests/{request_id}/reviews")
def get_review(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    existing_request = db.query(Requests).filter(Requests.request_id == request_id).first()
    if not existing_request:
        raise HTTPException(status_code=404, detail="Request not found.")

    is_owner = current_user.user_id == existing_request.requester_reference
    is_admin = current_user.role == "admin"
    # A reviewer who claimed the request, or who has already left a review on
    # it (e.g. before an admin overrode their decision), can see the review
    # history too — not just the original requester or an admin.
    is_involved_reviewer = current_user.role == "reviewer" and (
        current_user.user_id == existing_request.claimed_by
        or db.query(Reviews)
        .filter(
            Reviews.request_reference == request_id,
            Reviews.reviewer_reference == current_user.user_id,
        )
        .first()
        is not None
    )
    if not (is_owner or is_admin or is_involved_reviewer):
        raise HTTPException(status_code=403, detail="Not Authorized to see review.")
    return db.query(Reviews).filter(Reviews.request_reference == request_id).order_by(Reviews.reviewed_at).all()

# Derived from models.REQUEST_TYPES/PRIORITIES (the single source of truth
# also used by the DB check constraints and the chatbot's tool schemas) so
# this enum can't silently drift out of sync with what the DB actually
# accepts — see models.py for why that matters.
RequestTypeEnum = Enum(
    "RequestTypeEnum",
    {t.upper().replace("-", "_"): t for t in REQUEST_TYPES},
    type=str,
)

PriorityEnum = Enum(
    "PriorityEnum",
    {p: p for p in PRIORITIES},
    type=str,
)

class DecisionEnum(str, Enum):
    approved = "APPROVED"
    not_approved = "NOT APPROVED"

class RequestCreate(BaseModel):
    request_type: RequestTypeEnum
    description: str | None = Field(default=None, max_length=500)
    priority: PriorityEnum = PriorityEnum.P1
    urgency_justification: str | None = Field(default=None, max_length=300)

class SimilarityCheckRequest(BaseModel):
    request_type: RequestTypeEnum
    description: str = Field(max_length=500)

class ReviewCreate(BaseModel):
    request_reference: int
    decision: DecisionEnum
    comment_text: Optional[str] = None

class RoleEnum(str, Enum):
    requester = "requester"
    reviewer = "reviewer"
    admin = "admin"

class StatusEnum(str, Enum):
    open_request = "open"
    in_progress_request = "in-progress"
    closed_request = "closed"

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)
    role: RoleEnum = RoleEnum.requester

class UserLogin(BaseModel):
    email: str
    password: str

class StatusUpdate(BaseModel):
    status: StatusEnum 


    

@app.post("/requests")
def create_request(request: RequestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return create_request_for_user(
        db,
        current_user,
        request_type=request.request_type,
        description=request.description,
        priority=request.priority,
        urgency_justification=request.urgency_justification,
    ) # not looping through and returning all the requests because we are creating one request and confirming it got created


@app.post("/requests/check-similar")
def check_similar(payload: SimilarityCheckRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    enforce_rate_limit(f"check-similar:{current_user.user_id}", max_requests=20, window_seconds=60)
    matches = check_similar_requests(db, current_user, payload.request_type, payload.description)
    return {"matches": matches}


@app.patch("/requests/{request_id}/claim")
def claim_request(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["reviewer", "admin"]:
        raise HTTPException(status_code=403, detail="Only reviewers or admins can claim requests.")

    # Lock the row so two reviewers racing to claim the same request can't
    # both pass the status check before either commits.
    existing_request = (
        db.query(Requests).filter(Requests.request_id == request_id).with_for_update().first()
    )
    if not existing_request:
        raise HTTPException(status_code=404, detail="Request not found.")

    if existing_request.status != "open":
        raise HTTPException(status_code=400, detail="Only open (unclaimed) requests can be claimed.")

    existing_request.claimed_by = current_user.user_id
    existing_request.status = "in-progress"
    db.commit()
    db.refresh(existing_request)
    return existing_request


@app.patch("/requests/{request_id}/unclaim")
def unclaim_request(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    existing_request = (
        db.query(Requests).filter(Requests.request_id == request_id).with_for_update().first()
    )
    if not existing_request:
        raise HTTPException(status_code=404, detail="Request not found.")

    if existing_request.status != "in-progress":
        raise HTTPException(status_code=400, detail="Only claimed requests can be unclaimed.")

    if current_user.role != "admin" and existing_request.claimed_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Only the reviewer who claimed this request can unclaim it.")

    existing_request.claimed_by = None
    existing_request.status = "open"
    db.commit()
    db.refresh(existing_request)
    return existing_request


@app.post("/reviews")
def create_review(review: ReviewCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return create_review_for_user(
        db,
        current_user,
        request_reference=review.request_reference,
        decision=review.decision,
        comment_text=review.comment_text,
    )

@app.post("/users")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = User(
        name = user.name,
        email = user.email,
        password = hash_password(user.password),
        role = user.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"user_id": new_user.user_id, "name": new_user.name, "email": new_user.email, "role": new_user.role}

@app.post("/login")
def user_login(login: UserLogin, request: Request, db: Session = Depends(get_db)):
    # Keyed by client IP since there's no authenticated user yet — bounds
    # brute-force password guessing against a single account.
    enforce_rate_limit(f"login:{request.client.host}", max_requests=5, window_seconds=60)

    existing_user = db.query(User).filter(User.email == login.email).first()
    if not existing_user or not verify_password(login.password, existing_user.password):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    token = create_access_token({"sub": str(existing_user.user_id)})
    return {"access_token": token, "token_type": "bearer"}

@app.patch("/requests/{request_id}/status")
def update_request_status(request_id: int, status_update: StatusUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["reviewer", "admin"]:
        raise HTTPException(status_code=403,detail="Only reviewers or admins can update the request status.")

    existing_request = (
        db.query(Requests).filter(Requests.request_id == request_id).with_for_update().first()
    )
    if not existing_request:
        raise HTTPException(status_code=404, detail="Request not found.")

    # A request that has already been decided (approved/rejected) can only be
    # changed via POST /reviews' admin-only, comment-required override flow —
    # otherwise any reviewer could silently reopen a decided request through
    # this route and bypass that protection entirely.
    if existing_request.status in ("approved", "rejected"):
        raise HTTPException(
            status_code=400,
            detail="This request has already been decided. Use the review override flow to change its outcome.",
        )

    existing_request.status = status_update.status.value
    db.commit()
    db.refresh(existing_request)
    return existing_request

@app.get("/admin/analytics")
def admin_analytics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view analytics.")
    return get_admin_analytics(db)