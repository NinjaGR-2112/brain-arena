"""Inscription, connexion, déconnexion."""
from tests.helpers import register_and_login


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


# ---------------------------------------------------------------------------
# Déconnexion
# ---------------------------------------------------------------------------


def test_logout_redirects_to_home(client):
    """Le bouton du dashboard doit ramener à l'accueil, pas afficher du JSON."""
    register_and_login(client, "leaver")

    response = client.post("/logout", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_logout_clears_the_session(client):
    register_and_login(client, "seeyou")
    assert client.get("/auth/me").status_code == 200

    client.post("/logout")

    assert client.get("/auth/me").status_code == 401


def test_dashboard_logout_button_points_to_the_logout_route(client):
    """Régression : le formulaire pointait vers /auth/logout, une route d'API
    qui renvoie du JSON ; le navigateur affichait « {"message": "Logged out"} ».
    """
    register_and_login(client, "buttonchecker")

    html = client.get("/dashboard").text

    assert 'action="/logout"' in html
    assert "/auth/logout" not in html


def test_auth_logout_still_answers_json(client):
    """La route d'API reste inchangée pour les appels en JSON."""
    register_and_login(client, "apiuser")

    response = client.post("/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"message": "Logged out"}
    assert client.get("/auth/me").status_code == 401
