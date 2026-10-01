"""Utilitaires partagés par les tests."""
import base64
import json
import re

PASSWORD = "password123"


def register_and_login(client, username="testplayer", password=PASSWORD):
    """Inscrit puis connecte un utilisateur, en vérifiant que les deux appels passent."""
    register = client.post(
        "/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )
    assert register.status_code == 201, register.text

    login = client.post("/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200, login.text


def decode_session_cookie(cookie_value: str) -> dict:
    """Décode le contenu d'un cookie de session Starlette.

    Le cookie est signé, pas chiffré : cette fonction reproduit ce que peut
    faire n'importe quel client, et sert donc à vérifier que rien de sensible
    n'y transite.
    """
    return json.loads(base64.b64decode(cookie_value.split(".")[0]))


def sequence_from_page(html: str) -> str:
    """Extrait la séquence Memory telle qu'affichée dans la page."""
    match = re.search(r'id="sequence-display"[^>]*>\s*([0-9\s]+?)\s*</div>', html)
    assert match, "séquence Memory introuvable dans la page"
    return re.sub(r"\s+", "", match.group(1))


def get_user(db, username):
    """Utilisateur relu depuis la base, cache de session SQLAlchemy purgé."""
    from app.models.user import User

    db.expire_all()
    return db.query(User).filter_by(username=username).one()


def get_game_session(db, game_type):
    """Partie en cours relue depuis la base, cache de session purgé."""
    from app.models.game_session import GameSession

    db.expire_all()
    return db.query(GameSession).filter_by(game_type=game_type).one()
