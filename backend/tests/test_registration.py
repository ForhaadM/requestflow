def test_register_success(client):
    response = client.post(
        "/users",
        json={"name": "New User", "email": "newuser@example.com", "password": "pw12345"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "newuser@example.com"
    assert body["role"] == "requester"


def test_register_duplicate_email_rejected(client, registered_user):
    response = client.post(
        "/users",
        json={"name": "Someone Else", "email": registered_user["email"], "password": "differentpw"},
    )
    assert response.status_code == 400


def test_register_response_never_contains_password(client):
    response = client.post(
        "/users",
        json={"name": "New User", "email": "nopassword@example.com", "password": "pw12345"},
    )
    assert "password" not in response.json()


def test_register_invalid_email_rejected(client):
    response = client.post(
        "/users",
        json={"name": "Bad Email", "email": "not-an-email", "password": "pw12345"},
    )
    assert response.status_code == 422


def test_register_short_password_rejected(client):
    response = client.post(
        "/users",
        json={"name": "Short Pw", "email": "shortpw@example.com", "password": "abc"},
    )
    assert response.status_code == 422
