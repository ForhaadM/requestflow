from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import engine
from models import User, Requests, Reviews
from typing import Optional
from enum import Enum
from auth import hash_password

app = FastAPI()


def get_db():
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()

@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@app.get("/requests")
def get_requests(db: Session = Depends(get_db)):
    return db.query(Requests).all() # Show me all requests in the system (Useful for admin)


@app.get("/reviews")
def get_reviews(db: Session = Depends(get_db)):
    return db.query(Reviews).all()

class RequestCreate(BaseModel):
    requester_reference: int
    request_type: str
    description: str | None = None
    priority: str = "P1"

class ReviewCreate(BaseModel):
    request_reference: int
    reviewer_reference: int
    decision: str 
    comment_text: Optional[str] = None

class RoleEnum(str, Enum):
    requester = "requester"
    reviewer = "reviewer"
    admin = "admin"

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: RoleEnum = RoleEnum.requester 

    

@app.post("/requests")
def create_request(request: RequestCreate, db: Session = Depends(get_db)):
    new_request = Requests( 
        requester_reference=request.requester_reference,
        request_type=request.request_type,
        description=request.description,
        priority=request.priority
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return new_request # not looping through and returning all the requests because we are creating one request and confirming it got created


@app.post("/reviews")
def create_review(review: ReviewCreate, db: Session = Depends(get_db)):
    if review.decision == "NOT APPROVED" and not review.comment_text:
        raise HTTPException(status_code=400, detail="A comment is required when rejecting a request.")

    new_review = Reviews(
        request_reference=review.request_reference,
        reviewer_reference=review.reviewer_reference,
        decision=review.decision,
        comment_text=review.comment_text
    )
    db.add(new_review)
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

