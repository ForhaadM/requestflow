import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import rate_limit
from database import Base, get_db
from main import app


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Rate-limit state is a module-level, in-memory dict (see rate_limit.py)
    so it persists across the whole pytest session unless cleared — without
    this, fixtures like `make_user` that log in repeatedly would trip the
    login rate limit partway through the suite. Mirrors the per-test DB
    isolation `db_session` already provides."""
    rate_limit._hits.clear()
    yield

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
TEST_DB_NAME = f"{os.getenv('POSTGRES_DB')}_test"

ADMIN_DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/postgres"
)
TEST_DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{TEST_DB_NAME}"
)


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_database():
    """Create the requestflow_test database on the same Postgres server if it doesn't exist yet."""
    admin_engine = create_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": TEST_DB_NAME},
        ).first()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin_engine.dispose()


test_engine = create_engine(TEST_DATABASE_URL)


@pytest.fixture
def db_session():
    """A clean database schema for a single test, torn down afterward."""
    Base.metadata.create_all(bind=test_engine)
    session = Session(test_engine)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client(db_session):
    """A TestClient wired to the test database instead of the real one."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


TEST_USER = {
    "name": "Test User",
    "email": "testuser@example.com",
    "password": "testpass123",
}


@pytest.fixture
def test_credentials():
    """Exposes TEST_USER to test modules without needing a package-style import of conftest."""
    return TEST_USER


@pytest.fixture
def registered_user(client):
    """Registers TEST_USER via the real /users route and returns the response body."""
    response = client.post("/users", json=TEST_USER)
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def auth_token(client, registered_user):
    """Logs TEST_USER in via the real /login route and returns a valid JWT."""
    response = client.post(
        "/login",
        json={"email": TEST_USER["email"], "password": TEST_USER["password"]},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    """Ready-to-use Authorization header for hitting protected routes."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def make_user(client):
    """Factory fixture: make_user(role="admin") registers + logs in a fresh user
    with that role and returns their user_id and Authorization headers."""
    counter = {"n": 0}

    def _make_user(role="requester"):
        counter["n"] += 1
        email = f"user{counter['n']}@example.com"
        password = "password123"
        register_response = client.post(
            "/users",
            json={"name": f"User {counter['n']}", "email": email, "password": password, "role": role},
        )
        login_response = client.post("/login", json={"email": email, "password": password})
        token = login_response.json()["access_token"]
        return {
            "user_id": register_response.json()["user_id"],
            "headers": {"Authorization": f"Bearer {token}"},
        }

    return _make_user
