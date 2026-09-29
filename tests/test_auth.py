def test_register_creates_user(client):
    response = client.post("/auth/register", json={
        "username": "alice",
        "email": "alice@example.com",
        "password": "password123",
    })

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "alice"


def test_register_rejects_duplicate_username(client):
    client.post("/auth/register", json={
        "username": "bob",
        "email": "bob@example.com",
        "password": "password123",
    })

    response = client.post("/auth/register", json={
        "username": "bob",
        "email": "different@example.com",
        "password": "password123",
    })

    assert response.status_code == 400


def test_login_with_correct_credentials(client):
    client.post("/auth/register", json={
        "username": "carol",
        "email": "carol@example.com",
        "password": "password123",
    })

    response = client.post("/auth/login", json={
        "username": "carol",
        "password": "password123",
    })

    assert response.status_code == 200
    assert response.json()["username"] == "carol"


def test_login_with_wrong_password_fails(client):
    client.post("/auth/register", json={
        "username": "dave",
        "email": "dave@example.com",
        "password": "password123",
    })

    response = client.post("/auth/login", json={
        "username": "dave",
        "password": "wrongpassword",
    })

    assert response.status_code == 401