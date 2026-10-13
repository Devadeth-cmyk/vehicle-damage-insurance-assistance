def test_register_user(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Jane Doe",
            "email": "jane@example.com",
            "password": "SecurePassword123",
            "phone": "555-0199",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_register_duplicate_email(client):
    user_data = {
        "full_name": "Jane Doe",
        "email": "jane_dup@example.com",
        "password": "SecurePassword123",
    }
    client.post("/api/v1/auth/register", json=user_data)
    dup_res = client.post("/api/v1/auth/register", json=user_data)
    assert dup_res.status_code == 409


def test_login_user(client):
    user_data = {
        "full_name": "John Login",
        "email": "login@example.com",
        "password": "Password123!",
    }
    client.post("/api/v1/auth/register", json=user_data)

    res = client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@example.com",
            "password": "Password123!",
        },
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_invalid_credentials(client):
    res = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "WrongPassword",
        },
    )
    assert res.status_code == 401


def test_login_case_insensitive_email(client):
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Case User", "email": "Case.User@Example.com", "password": "Password123!"},
    )
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "case.user@example.com", "password": "Password123!"},
    )
    assert res.status_code == 200


def test_login_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Wrong Pw", "email": "wrongpw@example.com", "password": "Password123!"},
    )
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@example.com", "password": "nope-nope"},
    )
    assert res.status_code == 401


def test_swagger_form_login_and_me(client):
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Form User", "email": "form@example.com", "password": "Password123!"},
    )
    res = client.post(
        "/api/v1/auth/token",
        data={"username": "form@example.com", "password": "Password123!"},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "form@example.com"


def test_long_password_does_not_crash(client):
    pw = "A" * 100
    r = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Long Pw", "email": "long@example.com", "password": pw},
    )
    assert r.status_code == 201
    r = client.post("/api/v1/auth/login", json={"email": "long@example.com", "password": pw})
    assert r.status_code == 200
