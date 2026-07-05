from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import engine
from models import User, Requests, Reviews

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

class RequestCreate(BaseModel):
    requester_reference: int
    request_type: str
    description: str | None = None
    priority: str = "P1"

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
    return new_request
