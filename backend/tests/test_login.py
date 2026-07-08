def test_login_success(client, registered_user, test_credentials):
    response = client.post(
        "/login",
        json={"email": test_credentials["email"], "password": test_credentials["password"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password_rejected(client, registered_user, test_credentials):
    response = client.post(
        "/login",
        json={"email": test_credentials["email"], "password": "wrongpassword"},
    )
    assert response.status_code == 400
