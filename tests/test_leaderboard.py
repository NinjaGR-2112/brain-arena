def test_leaderboard_shows_registered_user(client):
    client.post("/auth/register", json={
        "username": "leaderplayer",
        "email": "leaderplayer@example.com",
        "password": "password123",
    })
    client.post("/auth/login", json={
        "username": "leaderplayer",
        "password": "password123",
    })

    response = client.get("/leaderboard")
    assert response.status_code == 200
    assert "leaderplayer" in response.text