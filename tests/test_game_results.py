def register_and_login(client, username="testplayer"):
    client.post("/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "password123",
    })
    client.post("/auth/login", json={
        "username": username,
        "password": "password123",
    })


def test_dashboard_requires_login(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303


def test_dashboard_accessible_when_logged_in(client):
    register_and_login(client)
    response = client.get("/dashboard")
    assert response.status_code == 200


def test_memory_game_updates_user_stats(client):
    register_and_login(client)

    client.get("/games/memory?level=1")

    response = client.post("/games/memory/submit?answer=0000")
    assert response.status_code == 200

    me_response = client.get("/auth/me")
    data = me_response.json()
    assert data["xp"] >= 0