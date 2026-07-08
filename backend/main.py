from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, EmailStr
from database import engine, get_db
from models import User, Requests, Reviews
from typing import Optional
from enum import Enum
from auth import hash_password, verify_password, create_access_token, get_current_user


# Request types that represent an issue being fixed rather than something being
# granted, so an "approval" means work was done and should say how.
ISSUE_REQUEST_TYPES = {"bug-report", "network", "facilities"}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/users")
def get_users(db: Session = Depends(get_db)):
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
    existing_request = db.query(Requests).filter(Requests.request_id == request_id).first()
    if not existing_request:
        raise HTTPException(status_code=404, detail="Request not found.")
    if current_user.role == "admin" or current_user.user_id == existing_request.requester_reference:
        return existing_request
    else:
        raise HTTPException(status_code=403, detail="Not Authorized to see request.")

@app.get("/requests/{request_id}/reviews")
def get_review(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    existing_request = db.query(Requests).filter(Requests.request_id == request_id).first()
    if not existing_request:
        raise HTTPException(status_code=404, detail="Request not found.")
    if current_user.role != "admin" and current_user.user_id != existing_request.requester_reference:
        raise HTTPException(status_code=403, detail="Not Authorized to see review.")
    return db.query(Reviews).filter(Reviews.request_reference == request_id).order_by(Reviews.reviewed_at).all()

class RequestTypeEnum(str, Enum):
    hardware = "hardware"
    software = "software"
    access_request = "access-request"
    account_password = "account-password"
    bug_report = "bug-report"
    network = "network"
    onboarding_offboarding = "onboarding-offboarding"
    facilities = "facilities"
    other = "other"

class PriorityEnum(str, Enum):
    p0 = "P0"
    p1 = "P1"
    p2 = "P2"
    p3 = "P3"

class DecisionEnum(str, Enum):
    approved = "APPROVED"
    not_approved = "NOT APPROVED"

class RequestCreate(BaseModel):
    request_type: RequestTypeEnum
    description: str | None = Field(default=None, max_length=500)
    priority: PriorityEnum = PriorityEnum.p1
    urgency_justification: str | None = Field(default=None, max_length=300)

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
    if not (request.description and request.description.strip()):
        raise HTTPException(status_code=400, detail="A description is required.")

    if request.priority == "P0" and not (request.urgency_justification and request.urgency_justification.strip()):
        raise HTTPException(status_code=400, detail="A justification is required for Urgent priority requests.")

    new_request = Requests(
        requester_reference=current_user.user_id,
        request_type=request.request_type,
        description=request.description,
        priority=request.priority,
        urgency_justification=request.urgency_justification
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return new_request # not looping through and returning all the requests because we are creating one request and confirming it got created


@app.patch("/requests/{request_id}/claim")
def claim_request(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["reviewer", "admin"]:
        raise HTTPException(status_code=403, detail="Only reviewers or admins can claim requests.")

    existing_request = db.query(Requests).filter(Requests.request_id == request_id).first()
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
    existing_request = db.query(Requests).filter(Requests.request_id == request_id).first()
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

    if current_user.role not in ["reviewer", "admin"]:
        raise HTTPException(status_code=403,detail="Only reviewers or admins can review requests.")

    existing_request = db.query(Requests).filter(Requests.request_id == review.request_reference).first()
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
        review.decision == "NOT APPROVED"
        or is_override
        or (review.decision == "APPROVED" and requires_resolution_notes)
    )

    if comment_required and not review.comment_text:
        if is_override:
            detail = "A comment is required when overriding a previous decision."
        elif review.decision == "APPROVED":
            detail = "A comment describing how this was resolved is required."
        else:
            detail = "A comment is required when rejecting a request."
        raise HTTPException(status_code=400, detail=detail)

    new_review = Reviews(
        request_reference=review.request_reference,
        reviewer_reference=current_user.user_id,
        decision=review.decision,
        comment_text=review.comment_text
    )
    db.add(new_review)

    existing_request.status = "approved" if review.decision == "APPROVED" else "rejected"

    db.commit()
    db.refresh(new_review)
    return new_review

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
def user_login(login: UserLogin, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == login.email).first()
    if not existing_user or not verify_password(login.password, existing_user.password):
        raise HTTPException(status_code=400, detail="Invalid email or password")
    
    token = create_access_token({"sub": str(existing_user.user_id)})
    return {"access_token": token, "token_type": "bearer"}

@app.patch("/requests/{request_id}/status")
def update_request_status(request_id: int, status_update: StatusUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["reviewer", "admin"]:
        raise HTTPException(status_code=403,detail="Only reviewers or admins can update the request status.") 
    
    existing_request = db.query(Requests).filter(Requests.request_id == request_id).first()
    if not existing_request:
        raise HTTPException(status_code=404, detail="Request not found.")

    existing_request.status = status_update.status.value
    db.commit()
    db.refresh(existing_request)
    return existing_request