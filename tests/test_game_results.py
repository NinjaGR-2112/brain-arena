"""Persistance des parties et protection des pages."""
from app.models.game_result import GameResult
from tests.helpers import get_user, register_and_login, sequence_from_page


def test_dashboard_requires_login(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303


def test_dashboard_accessible_when_logged_in(client):
    register_and_login(client)
    assert client.get("/dashboard").status_code == 200


def test_memory_game_updates_user_stats(client, db):
    """Une partie juste doit réellement créditer score, XP et compteur.

    L'ancienne version de ce test se contentait de ``assert data["xp"] >= 0``,
    vraie même si rien n'était crédité.
    """
    register_and_login(client, "testplayer")

    page = client.get("/games/memory?level=1")
    answer = sequence_from_page(page.text)
    before = get_user(db, "testplayer")
    assert (before.xp, before.total_score, before.games_played) == (0, 0, 0)

    result = client.post(f"/games/memory/submit?answer={answer}").json()
    assert result["correct"] is True
    assert result["score"] > 0
    assert result["xp_earned"] > 0

    after = get_user(db, "testplayer")
    assert after.xp == result["xp_earned"]
    assert after.total_score == result["score"]
    assert after.games_played == 1


def test_memory_wrong_answer_records_a_zero_score_game(client, db):
    register_and_login(client, "wronganswer")

    client.get("/games/memory?level=1")
    client.post("/games/memory/submit?answer=")

    result = get_user(db, "wronganswer")
    assert result.total_score == 0
    assert result.games_played == 1


def test_memory_game_result_row_is_written(client, db):
    register_and_login(client, "persisted")

    page = client.get("/games/memory?level=2")
    answer = sequence_from_page(page.text)
    client.post(f"/games/memory/submit?answer={answer}")

    db.expire_all()
    rows = db.query(GameResult).all()
    assert len(rows) == 1
    assert rows[0].game_type == "memory"
    assert rows[0].duration > 0


def test_password_hash_is_never_returned(client):
    register_and_login(client, "secretive")

    assert "password" not in client.get("/auth/me").json()
    assert "password_hash" not in client.get("/dashboard").text
