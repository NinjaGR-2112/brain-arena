"""Classement : contenu, pagination, rang personnel."""
from fastapi.testclient import TestClient

from tests.helpers import register_and_login, sequence_from_page


def play_one_memory_game(client, username):
    """Joue une partie de Memory juste, pour faire gagner de l'XP."""
    register_and_login(client, username)
    page = client.get("/games/memory?level=1")
    answer = sequence_from_page(page.text)
    return client.post(f"/games/memory/submit?answer={answer}").json()


def test_leaderboard_requires_login(client):
    assert client.get("/leaderboard", follow_redirects=False).status_code == 303


def test_leaderboard_shows_registered_user(client):
    register_and_login(client, "leaderplayer")

    response = client.get("/leaderboard")

    assert response.status_code == 200
    assert "leaderplayer" in response.text


def test_leaderboard_is_ordered_by_xp(client):
    first = TestClient(client.app)
    play_one_memory_game(first, "firstxp")

    second = TestClient(client.app)
    play_one_memory_game(second, "secondxp")

    register_and_login(client, "lowxp")  # 0 XP

    page = client.get("/leaderboard")
    assert page.text.index("firstxp") < page.text.index("secondxp")
    assert page.text.index("secondxp") < page.text.index("lowxp")


def test_leaderboard_reports_personal_rank(client):
    register_and_login(client, "ranked")

    assert "Your rank: 1" in client.get("/leaderboard").text
