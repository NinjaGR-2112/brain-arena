"""Tests anti-triche.

Chaque test correspond à une faille réellement reproduite avant correctif :
rejeu de cookie, niveau hors bornes, état lisible côté client, minuteur
purement navigateur, appel /finish sans partie, temps de réaction impossible.
"""
import json
import time
from datetime import timedelta

from fastapi.testclient import TestClient

from app.games.calculation import MAX_CORRECT_ANSWERS
from app.games.memory import LEVELS as MEMORY_LEVELS
from app.games.memory import LEVEL_LENGTHS
from app.models.user import User
from app.services.game_sessions import get_active_game_session
from app.utils.time import utcnow
from tests.helpers import (
    decode_session_cookie,
    get_game_session,
    get_user,
    register_and_login,
    sequence_from_page,
)


# ---------------------------------------------------------------------------
# Rejeu : un même jeton ne peut créditer qu'une seule partie
# ---------------------------------------------------------------------------


def test_memory_game_cannot_be_replayed(client, db):
    """Régression : rejouer un ancien cookie créditait une nouvelle partie."""
    register_and_login(client, "replayer")

    page = client.get("/games/memory?level=1")
    answer = sequence_from_page(page.text)
    saved_cookie = client.cookies["session"]

    assert client.post(f"/games/memory/submit?answer={answer}").status_code == 200

    client.cookies.set("session", saved_cookie)
    assert client.post(f"/games/memory/submit?answer={answer}").status_code == 400

    assert get_user(db, "replayer").games_played == 1


def test_memory_replay_does_not_double_the_xp(client):
    """Régression : 5 rejeux créditaient 5 parties et 245 XP."""
    register_and_login(client, "farmer")

    page = client.get("/games/memory?level=4")
    answer = sequence_from_page(page.text)
    saved_cookie = client.cookies["session"]

    first = client.post(f"/games/memory/submit?answer={answer}").json()
    xp_after_first = client.get("/auth/me").json()["xp"]
    assert first["xp_earned"] > 0
    assert xp_after_first == first["xp_earned"]

    for _ in range(5):
        client.cookies.set("session", saved_cookie)
        assert client.post(f"/games/memory/submit?answer={answer}").status_code == 400

    assert client.get("/auth/me").json()["xp"] == xp_after_first


def test_calculation_finish_without_a_game_is_refused(client):
    """Régression : /finish créait une partie et incrémentait games_played."""
    register_and_login(client, "spammer")

    for _ in range(3):
        assert client.post("/games/calculation/finish").status_code == 400

    assert client.get("/auth/me").json()["xp"] == 0


def test_calculation_finish_counts_exactly_one_game(client, db):
    register_and_login(client, "onestart")

    client.get("/games/calculation?level=1")
    assert client.post("/games/calculation/finish").status_code == 200
    assert client.post("/games/calculation/finish").status_code == 400

    assert get_user(db, "onestart").games_played == 1


# ---------------------------------------------------------------------------
# L'état sensible ne transite plus par le client
# ---------------------------------------------------------------------------


def test_cookie_does_not_leak_game_state(client):
    """Régression : la séquence et la bonne réponse étaient lisibles en base64."""
    register_and_login(client, "reader")

    client.get("/games/memory?level=1")
    assert decode_session_cookie(client.cookies["session"]) == {
        "user_id": client.get("/auth/me").json()["id"],
        "game_token": decode_session_cookie(client.cookies["session"])["game_token"],
    }

    client.get("/games/calculation?level=1")
    calc_cookie = decode_session_cookie(client.cookies["session"])
    assert "calc_answer" not in calc_cookie
    assert "answer" not in calc_cookie

    client.get("/games/reaction")
    reaction_cookie = decode_session_cookie(client.cookies["session"])
    assert "reaction_signal_time" not in reaction_cookie
    assert "scores" not in reaction_cookie


def test_calculation_response_never_contains_the_answer(client):
    register_and_login(client, "peeker")
    client.get("/games/calculation?level=1")

    data = client.post("/games/calculation/answer?value=0").json()

    assert set(data["next_operation"]) == {"a", "b", "op"}


def test_game_session_token_is_bound_to_its_owner(client, db):
    """Un jeton ne vaut que pour son propriétaire et pour son type de jeu."""
    register_and_login(client, "owner")
    client.get("/games/memory?level=1")

    token = decode_session_cookie(client.cookies["session"])["game_token"]
    owner_id = client.get("/auth/me").json()["id"]

    thief = User(username="thief", email="thief@example.com", password_hash="not-a-hash")
    db.add(thief)
    db.commit()

    assert get_active_game_session(db, token=token, user_id=owner_id, game_type="memory")
    assert get_active_game_session(db, token=token, user_id=thief.id, game_type="memory") is None
    assert (
        get_active_game_session(db, token=token, user_id=owner_id, game_type="calculation") is None
    )


# ---------------------------------------------------------------------------
# Niveau borné côté serveur
# ---------------------------------------------------------------------------


def test_memory_level_above_the_maximum_is_clamped(client):
    """Régression : ?level=1000000 rapportait 100 000 099 points."""
    register_and_login(client, "whale")

    page = client.get("/games/memory?level=1000000")
    answer = sequence_from_page(page.text)
    result = client.post(f"/games/memory/submit?answer={answer}").json()

    assert max(MEMORY_LEVELS) == 4
    assert len(answer) == LEVEL_LENGTHS[max(MEMORY_LEVELS)]  # ramené au niveau 4, pas inventé
    assert result["score"] <= 500  # 4 * 100 + bonus de vitesse maximal (100)


def test_memory_negative_level_is_clamped(client, db):
    register_and_login(client, "negative")

    page = client.get("/games/memory?level=-50")
    answer = sequence_from_page(page.text)
    assert client.post(f"/games/memory/submit?answer={answer}").status_code == 200

    assert get_game_session(db, "memory").level == min(MEMORY_LEVELS)


def test_calculation_level_above_the_maximum_is_clamped(client, db):
    """Régression : level=1000000 rapportait 20 000 000 points pour une réponse."""
    register_and_login(client, "calcwhale")

    page = client.get("/games/calculation?level=1000000")
    assert "Level 3" in page.text

    client.post("/games/calculation/answer?value=0")
    result = client.post("/games/calculation/finish").json()

    assert result["correct_count"] <= 1
    assert result["score"] <= 20 * 3  # une bonne réponse au niveau 3


# ---------------------------------------------------------------------------
# Minuteur serveur : les 30 secondes ne dépendent plus du navigateur
# ---------------------------------------------------------------------------


def test_calculation_is_refused_after_the_deadline(client, db):
    """Régression : le minuteur de 30 s n'existait que côté client."""
    register_and_login(client, "lateplayer")
    client.get("/games/calculation?level=1")

    row = get_game_session(db, "calculation")
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()

    assert client.post("/games/calculation/answer?value=0").status_code == 400
    assert client.post("/games/calculation/finish").status_code == 400


def test_calculation_finish_is_allowed_within_the_grace_period(client):
    """Le minuteur du navigateur se déclenche à 30 s ; la latence réseau ne
    doit pas faire perdre la partie au joueur honnête."""
    register_and_login(client, "honest")
    client.get("/games/calculation?level=1")

    assert client.post("/games/calculation/finish").status_code == 200


def test_calculation_rapid_fire_answers_are_throttled(client):
    register_and_login(client, "rapidfire")
    client.get("/games/calculation?level=1")

    accepted = 0
    for _ in range(40):
        data = client.post("/games/calculation/answer?value=0").json()
        if not data["too_fast"]:
            accepted += 1

    assert accepted < 40


def test_calculation_correct_count_is_capped(client, db):
    """Le compteur de bonnes réponses est plafonné, quel que soit le débit."""
    register_and_login(client, "capped")
    client.get("/games/calculation?level=1")

    row = get_game_session(db, "calculation")
    state = json.loads(row.state)
    state["correct_count"] = MAX_CORRECT_ANSWERS
    state["last_answer_at"] = None
    row.state = json.dumps(state)
    db.commit()

    client.post("/games/calculation/answer?value=0")
    result = client.post("/games/calculation/finish").json()

    assert result["correct_count"] == MAX_CORRECT_ANSWERS


# ---------------------------------------------------------------------------
# Reaction : temps physiquement impossibles
# ---------------------------------------------------------------------------


def test_reaction_impossible_times_score_zero(client, monkeypatch):
    """Régression : un client automatisé obtenait 994/1000 et 99 XP."""
    register_and_login(client, "reactionbot")
    monkeypatch.setattr("app.routes.pages.generate_delay", lambda: 0.01)

    client.get("/games/reaction")

    final = None
    for _ in range(5):
        client.post("/games/reaction/wait")
        data = client.post("/games/reaction/click").json()
        assert data["too_fast"] is True
        assert data["round_score"] == 0
        final = data

    assert final["game_finished"] is True
    assert final["final_score"] == 0
    assert final["xp_earned"] == 0


def test_reaction_plausible_times_are_scored(client, monkeypatch):
    """Le garde-fou ne doit pas pénaliser un joueur humain."""
    register_and_login(client, "humanish")
    monkeypatch.setattr("app.routes.pages.generate_delay", lambda: 0.01)

    client.get("/games/reaction")

    final = None
    for _ in range(5):
        client.post("/games/reaction/wait")
        time.sleep(0.15)  # au-dessus du seuil humain de 120 ms
        final = client.post("/games/reaction/click").json()
        assert final["too_fast"] is False
        assert final["round_score"] > 0

    assert final["game_finished"] is True
    assert final["final_score"] > 0
    assert final["xp_earned"] > 0


def test_reaction_second_click_without_signal_is_refused(client, monkeypatch):
    register_and_login(client, "doubleclick")
    monkeypatch.setattr("app.routes.pages.generate_delay", lambda: 0.01)

    client.get("/games/reaction")
    client.post("/games/reaction/wait")
    time.sleep(0.15)

    assert client.post("/games/reaction/click").status_code == 200
    assert client.post("/games/reaction/click").status_code == 400


# ---------------------------------------------------------------------------
# Entrées du classement
# ---------------------------------------------------------------------------


def test_leaderboard_rejects_invalid_pages(client):
    register_and_login(client, "pager")

    assert client.get("/leaderboard?page=0").status_code == 422
    assert client.get("/leaderboard?page=-1").status_code == 422
    assert client.get("/leaderboard?page=1").status_code == 200


def test_unauthenticated_game_endpoints_redirect(client):
    for url in (
        "/games/memory/submit?answer=1234",
        "/games/reaction/click",
        "/games/calculation/finish",
    ):
        assert client.post(url, follow_redirects=False).status_code == 303
