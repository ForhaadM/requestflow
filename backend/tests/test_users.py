def test_get_users_requires_auth(client):
    response = client.get("/users")
    assert response.status_code == 401


def test_get_users_forbidden_for_requester(client, auth_headers):
    response = client.get("/users", headers=auth_headers)
    assert response.status_code == 403


def test_get_users_allowed_for_reviewer(client, make_user):
    reviewer = make_user(role="reviewer")
    response = client.get("/users", headers=reviewer["headers"])
    assert response.status_code == 200


def test_get_users_returns_registered_users_for_admin(client, registered_user, make_user):
    admin = make_user(role="admin")
    response = client.get("/users", headers=admin["headers"])
    assert response.status_code == 200
    emails = [user["email"] for user in response.json()]
    assert registered_user["email"] in emails


def test_get_users_response_never_contains_password(client, make_user):
    admin = make_user(role="admin")
    response = client.get("/users", headers=admin["headers"])
    for user in response.json():
        assert "password" not in user


def test_get_current_user_profile_requires_auth(client):
    response = client.get("/users/me")
    assert response.status_code == 401


def test_get_current_user_profile_returns_own_profile(client, registered_user, auth_headers):
    response = client.get("/users/me", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == registered_user["user_id"]
    assert body["email"] == registered_user["email"]
    assert "password" not in body


def test_get_current_user_profile_reflects_role(client, make_user):
    reviewer = make_user(role="reviewer")
    response = client.get("/users/me", headers=reviewer["headers"])
    assert response.status_code == 200
    assert response.json()["role"] == "reviewer"
