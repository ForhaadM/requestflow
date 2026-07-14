from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from jose import jwt

from auth import ALGORITHM, SECRET_KEY, create_access_token, get_current_user, hash_password, verify_password
from timeutils import utcnow


def test_hash_password_does_not_return_plaintext():
    hashed = hash_password("mypassword")
    assert hashed != "mypassword"


def test_hash_password_is_salted():
    hashed_once = hash_password("mypassword")
    hashed_again = hash_password("mypassword")
    assert hashed_once != hashed_again


def test_verify_password_correct():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_password_incorrect():
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False


def test_create_access_token_contains_sub_claim():
    token = create_access_token({"sub": "42"})
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "42"


def test_create_access_token_sets_future_expiry():
    token = create_access_token({"sub": "42"})
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    expire = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    assert expire > utcnow()
    assert expire < utcnow() + timedelta(minutes=31)


def test_get_current_user_invalid_token_rejected(db_session):
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token="not-a-valid-token", db=db_session)
    assert exc_info.value.status_code == 401


def test_get_current_user_unknown_user_rejected(db_session):
    token = create_access_token({"sub": "999999"})
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=token, db=db_session)
    assert exc_info.value.status_code == 401


def test_get_current_user_missing_sub_claim_rejected(db_session):
    token = create_access_token({})
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=token, db=db_session)
    assert exc_info.value.status_code == 401
