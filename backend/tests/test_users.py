def test_get_users_returns_registered_users(client, registered_user):
    response = client.get("/users")
    assert response.status_code == 200
    emails = [user["email"] for user in response.json()]
    assert registered_user["email"] in emails
