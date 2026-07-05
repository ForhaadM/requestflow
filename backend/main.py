from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import engine
from models import User, Requests, Reviews
from typing import Optional

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
