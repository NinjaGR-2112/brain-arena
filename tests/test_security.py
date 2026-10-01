"""Tests de la couche sécurité : sessions, mots de passe, login."""
import base64
import json
import os
import subprocess
import sys

import itsdangerous
from fastapi.testclient import TestClient

from tests.helpers import PASSWORD, decode_session_cookie, register_and_login

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# SECRET_KEY : démarrage refusé plutôt que sessions signées avec "None"
# ---------------------------------------------------------------------------


def _import_app_with_env(**extra):
    """Importe app.main dans un sous-processus, avec un environnement maîtrisé."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("SECRET_KEY", "DATABASE_URL")
    }
    env.update(extra)
    return subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_app_refuses_to_start_without_secret_key():
    # SECRET_KEY="" est posé explicitement : load_dotenv() n'écrase pas une
    # variable déjà présente, donc un éventuel .env local ne masque pas le test.
    result = _import_app_with_env(SECRET_KEY="")

    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr


def test_app_refuses_to_start_with_a_weak_secret_key():
    result = _import_app_with_env(SECRET_KEY="trop-courte")

    assert result.returncode != 0
    assert "too short" in result.stderr


# ---------------------------------------------------------------------------
# Falsification de session
# ---------------------------------------------------------------------------


def test_session_forged_with_the_default_none_key_is_rejected(client):
    """Régression : sans SECRET_KEY, Starlette signait avec la chaîne "None".

    N'importe qui pouvait alors forger {"user_id": 1} et accéder à n'importe
    quel compte. Avec une vraie clé, la signature ne vérifie plus.
    """
    register_and_login(client, "victim")
    user_id = client.get("/auth/me").json()["id"]

    forged = itsdangerous.TimestampSigner("None").sign(
        base64.b64encode(json.dumps({"user_id": user_id}).encode())
    ).decode()

    attacker = TestClient(client.app)
    attacker.cookies.set("session", forged)

    response = attacker.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert "Welcome" not in response.text


def test_tampered_session_cookie_is_rejected(client):
    register_and_login(client, "tamperer")

    payload = decode_session_cookie(client.cookies["session"])
    payload["user_id"] = payload["user_id"] + 999
    forged = itsdangerous.TimestampSigner("guessed-key").sign(
        base64.b64encode(json.dumps(payload).encode())
    ).decode()
    client.cookies.clear()
    client.cookies.set("session", forged)

    assert client.get("/dashboard", follow_redirects=False).status_code == 303
    assert client.get("/auth/me").status_code == 401


# ---------------------------------------------------------------------------
# Mots de passe : limite bcrypt de 72 octets
# ---------------------------------------------------------------------------


def test_register_rejects_overlong_password_with_422_not_500(client):
    """Régression : bcrypt 5.0.0 lève ValueError au-delà de 72 octets."""
    response = client.post(
        "/auth/register",
        json={"username": "longpass", "email": "longpass@example.com", "password": "x" * 100},
    )

    assert response.status_code == 422
    assert "72" in response.text


def test_register_accepts_password_at_the_bcrypt_limit(client):
    response = client.post(
        "/auth/register",
        json={"username": "edgepass", "email": "edgepass@example.com", "password": "x" * 72},
    )

    assert response.status_code == 201


def test_register_rejects_accented_password_over_the_byte_limit(client):
    # 36 « é » = 72 octets (accepté), 37 = 74 octets (refusé).
    accepted = client.post(
        "/auth/register",
        json={"username": "acc36", "email": "acc36@example.com", "password": "é" * 36},
    )
    rejected = client.post(
        "/auth/register",
        json={"username": "acc37", "email": "acc37@example.com", "password": "é" * 37},
    )

    assert accepted.status_code == 201, accepted.text
    assert rejected.status_code == 422


def test_login_with_overlong_password_fails_cleanly_not_500(client):
    register_and_login(client, "safeuser")

    response = client.post(
        "/auth/login", json={"username": "safeuser", "password": "x" * 200}
    )

    assert response.status_code == 401


def test_login_with_overlong_password_against_unknown_user_fails_cleanly(client):
    response = client.post(
        "/auth/login", json={"username": "no-such-user", "password": "x" * 200}
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Énumération de comptes par temps de réponse
# ---------------------------------------------------------------------------


def test_login_hashes_even_for_unknown_user(client, monkeypatch):
    """Le chemin « utilisateur inconnu » doit coûter le même temps.

    Mesuré avant correctif : 231 ms pour un compte existant contre 4,5 ms
    pour un compte inexistant.
    """
    calls = []
    monkeypatch.setattr("app.routes.auth.dummy_verify", lambda password: calls.append(password))

    response = client.post(
        "/auth/login", json={"username": "ghost-user", "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert len(calls) == 1


def test_login_hashing_is_not_wasted_on_known_user(client, monkeypatch):
    register_and_login(client, "knownuser")

    calls = []
    monkeypatch.setattr("app.routes.auth.dummy_verify", lambda password: calls.append(password))

    response = client.post("/auth/login", json={"username": "knownuser", "password": "wrong"})

    assert response.status_code == 401
    assert calls == []


def test_error_message_does_not_reveal_which_credential_is_wrong(client):
    register_and_login(client, "discreet")

    bad_password = client.post(
        "/auth/login", json={"username": "discreet", "password": "wrong"}
    ).json()["detail"]
    bad_username = client.post(
        "/auth/login", json={"username": "nobody-here", "password": PASSWORD}
    ).json()["detail"]

    assert bad_password == bad_username
