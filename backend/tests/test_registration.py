def test_register_success(client):
    response = client.post(
        "/users",
        json={"name": "New User", "email": "newuser@example.com", "password": "Pw123456!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "newuser@example.com"
    assert body["role"] == "requester"


def test_register_duplicate_email_rejected(client, registered_user):
    response = client.post(
        "/users",
        json={"name": "Someone Else", "email": registered_user["email"], "password": "Different1!"},
    )
    assert response.status_code == 400


def test_register_response_never_contains_password(client):
    response = client.post(
        "/users",
        json={"name": "New User", "email": "nopassword@example.com", "password": "Pw123456!"},
    )
    assert "password" not in response.json()


def test_register_invalid_email_rejected(client):
    response = client.post(
        "/users",
        json={"name": "Bad Email", "email": "not-an-email", "password": "Pw123456!"},
    )
    assert response.status_code == 422


def test_register_short_password_rejected(client):
    response = client.post(
        "/users",
        json={"name": "Short Pw", "email": "shortpw@example.com", "password": "Ab1!"},
    )
    assert response.status_code == 422


def test_register_password_without_uppercase_rejected(client):
    response = client.post(
        "/users",
        json={"name": "No Upper", "email": "noupper@example.com", "password": "lowercase1!"},
    )
    assert response.status_code == 422


def test_register_password_without_lowercase_rejected(client):
    response = client.post(
        "/users",
        json={"name": "No Lower", "email": "nolower@example.com", "password": "UPPERCASE1!"},
    )
    assert response.status_code == 422


def test_register_password_without_number_rejected(client):
    response = client.post(
        "/users",
        json={"name": "No Number", "email": "nonumber@example.com", "password": "NoNumbers!"},
    )
    assert response.status_code == 422


def test_register_password_without_special_char_rejected(client):
    response = client.post(
        "/users",
        json={"name": "No Special", "email": "nospecial@example.com", "password": "NoSpecial1"},
    )
    assert response.status_code == 422


def test_register_name_with_digits_rejected(client):
    response = client.post(
        "/users",
        json={"name": "User123", "email": "digitname@example.com", "password": "Pw123456!"},
    )
    assert response.status_code == 422


def test_register_name_with_symbols_rejected(client):
    response = client.post(
        "/users",
        json={"name": "User@Name", "email": "symbolname@example.com", "password": "Pw123456!"},
    )
    assert response.status_code == 422


def test_register_accented_name_accepted(client):
    response = client.post(
        "/users",
        json={"name": "José García", "email": "jose@example.com", "password": "Pw123456!"},
    )
    assert response.status_code == 200


def test_register_hyphenated_apostrophe_name_accepted(client):
    response = client.post(
        "/users",
        json={"name": "Mary-Jane O'Brien", "email": "maryjane@example.com", "password": "Pw123456!"},
    )
    assert response.status_code == 200


def test_register_name_with_leading_trailing_space_rejected(client):
    response = client.post(
        "/users",
        json={"name": " Padded Name ", "email": "padded@example.com", "password": "Pw123456!"},
    )
    assert response.status_code == 422
