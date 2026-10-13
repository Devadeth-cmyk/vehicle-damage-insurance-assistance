def test_get_user_profile(client, auth_headers):
    response = client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "testuser@example.com"
    assert data["full_name"] == "Test User"
    assert data["role"] == "user"
    assert data["is_active"] is True


def test_get_user_profile_unauthorized(client):
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
