from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from database import get_db
from models import User
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import timedelta
from jose import jwt, JWTError
from dotenv import load_dotenv
from timeutils import utcnow
import os

load_dotenv()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # Fail fast at import time (app boot) instead of on the first login
    # attempt, where a None SECRET_KEY produces a confusing jose error deep
    # inside jwt.encode.
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. Set it in your .env "
        "(see .env.example) before starting the app."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = utcnow() + timedelta(minutes = ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm = ALGORITHM)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms = [ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail = "Invalid Token")
    except JWTError:
        raise HTTPException(status_code=401, detail = "Invalid Token")

    user = db.query(User).filter(User.user_id == int(user_id)).first()    
    if user is None:
        raise HTTPException(status_code=401, detail = "User not found")

    return user