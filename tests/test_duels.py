"""Duels contre les bots : deroule, reglement, limites.

Le duel est un habillage par-dessus les parties existantes : le joueur joue
vraiment la partie, avec les mêmes routes, le même jeton à usage unique et le
même crédit de score/XP. Le duel n'ajoute qu'un adversaire, un niveau interne
et une prime de victoire.
"""
import time
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.models.duel import (
    STATUS_DRAWN,
    STATUS_EXPIRED,
    STATUS_LOST,
    STATUS_PENDING,
    STATUS_WON,
    Duel,
)
from app.services import duels
from app.services.duels import DuelError
from app.utils.time import utcnow
from tests.helpers import get_user, register_and_login, sequence_from_page


def start_duel(client, game_type):
    return client.post(
        "/duels/start", data={"game_type": game_type}, follow_redirects=False
    )


def duel_id_of(response):
    return int(response.headers["location"].split("duel_id=")[1])


def play_memory(client, duel_id, url=""):
    page = client.get(f"/games/memory?duel_id={duel_id}{url}")
    answer = sequence_from_page(page.text)
    return client.post(f"/games/memory/submit?answer={answer}&duel_id={duel_id}")


# ---------------------------------------------------------------------------
# Page et entrée
# ---------------------------------------------------------------------------


def test_duels_page_requires_login(client):
    assert client.get("/duels", follow_redirects=False).status_code == 303


def test_duels_page_offers_the_three_games(client):
    register_and_login(client, "challenger")

    html = client.get("/duels").text

    for game_type in ("memory", "reaction", "calculation"):
        assert f'value="{game_type}"' in html


def test_starting_a_duel_creates_a_pending_duel(client, db):
    register_and_login(client, "starter")

    response = start_duel(client, "memory")

    assert response.status_code == 303
    assert "/games/memory?duel_id=" in response.headers["location"]
    row = db.query(Duel).one()
    assert row.status == STATUS_PENDING
    assert row.game_type == "memory"
    assert row.bot_score >= 0
    assert row.bot_name


def test_unknown_game_type_is_refused(client, db):
    register_and_login(client, "typo")

    assert start_duel(client, "chess").status_code == 400
    assert db.query(Duel).count() == 0


def test_duel_start_requires_login(client):
    assert start_duel(client, "memory").status_code == 303


# ---------------------------------------------------------------------------
# Le niveau reste interne
# ---------------------------------------------------------------------------


def test_duel_level_is_never_shown_to_the_player(client):
    """Regression : le joueur ne doit plus voir ni choisir de niveau."""
    register_and_login(client, "blind")
    duel_id = duel_id_of(start_duel(client, "memory"))

    page = client.get(f"/games/memory?duel_id={duel_id}").text
    listing = client.get("/duels").text

    assert "Level" not in page
    assert "level" not in listing.lower()
    assert "rookie" not in page.lower()
    assert "difficulty" not in page.lower()


def test_duel_level_is_shared_by_player_and_bot(client, db, monkeypatch):
    """Meme niveau des deux cotes : sinon le duel n'est pas equitable."""
    register_and_login(client, "fair")
    monkeypatch.setattr(
        "app.services.duels.pick_difficulty", lambda xp, rng=None: "elite"
    )
    duel_id = duel_id_of(start_duel(client, "memory"))
    duel = db.get(Duel, duel_id)

    page = client.get(f"/games/memory?duel_id={duel_id}")

    assert duel.level == 4
    # Niveau 4 de Memory : une sequence de 7 chiffres, pas 4.
    assert len(sequence_from_page(page.text)) == 7


def test_a_level_param_cannot_inflate_a_duel(client, db, monkeypatch):
    """Regression : ?level=1000000 rapportait 100 000 099 points."""
    register_and_login(client, "whale")
    monkeypatch.setattr(
        "app.services.duels.pick_difficulty", lambda xp, rng=None: "rookie"
    )
    duel_id = duel_id_of(start_duel(client, "memory"))

    client.get(f"/games/memory?duel_id={duel_id}&level=1000000")

    assert db.get(Duel, duel_id).level == 1
    assert get_user(db, "whale").total_score == 0


# ---------------------------------------------------------------------------
# Reglement
# ---------------------------------------------------------------------------


def test_memory_duel_win_is_settled(client, db, monkeypatch):
    register_and_login(client, "duelist")
    monkeypatch.setattr("app.services.duels.bot_score", lambda *a, **k: 0)
    monkeypatch.setattr(
        "app.services.duels.pick_difficulty", lambda xp, rng=None: "regular"
    )
    duel_id = duel_id_of(start_duel(client, "memory"))

    data = play_memory(client, duel_id).json()["duel"]

    assert data["outcome"] == STATUS_WON
    assert data["bot_score"] == 0
    assert data["player_score"] > 0


def test_memory_duel_loss_is_settled(client, db, monkeypatch):
    register_and_login(client, "loser")
    monkeypatch.setattr("app.services.duels.bot_score", lambda *a, **k: 999_999)
    duel_id = duel_id_of(start_duel(client, "memory"))

    data = play_memory(client, duel_id).json()["duel"]

    assert data["outcome"] == STATUS_LOST


def test_memory_duel_draw_is_settled(client, db):
    """Match nul : même score des deux côtés.

    Testé au niveau du service, pas de la route : la route règle le duel avec
    le score du joueur, or ce score dépend de sa vitesse de réponse. Ici on
    maîtrise les deux valeurs, ce qui est la seule façon de obtenir un nul
    de façon déterministe.
    """
    register_and_login(client, "drawer")
    user = get_user(db, "drawer")
    duel = Duel(
        user_id=user.id,
        game_type="memory",
        difficulty="rookie",
        level=1,
        bot_name="Volt",
        bot_score=250,
        status=STATUS_PENDING,
        expires_at=utcnow() + timedelta(hours=1),
    )
    db.add(duel)
    db.commit()

    outcome = duels.settle_duel(db, duel, user, 250)

    assert outcome["outcome"] == STATUS_DRAWN
    assert outcome["player_score"] == 250
    assert outcome["bot_score"] == 250


def test_a_stronger_player_score_beats_the_bot(client, db):
    """Le règlement compare bien les scores, dans le bon sens."""
    register_and_login(client, "beater")
    user = get_user(db, "beater")

    def a_duel(bot_score):
        duel = Duel(
            user_id=user.id,
            game_type="memory",
            difficulty="rookie",
            level=1,
            bot_name="Volt",
            bot_score=bot_score,
            status=STATUS_PENDING,
            expires_at=utcnow() + timedelta(hours=1),
        )
        db.add(duel)
        db.commit()
        return duel

    assert duels.settle_duel(db, a_duel(100), user, 101)["outcome"] == STATUS_WON
    assert duels.settle_duel(db, a_duel(100), user, 99)["outcome"] == STATUS_LOST


def test_calculation_duel_settles_on_finish(client, db, monkeypatch):
    register_and_login(client, "calculator")
    # Le bot marque 1 point de moins que le score minimal d'une partie finie
    # sans bonne réponse (0), ce qui est impossible : on le met à -1 pour que
    # le joueur, même à 0, gagne le duel.
    monkeypatch.setattr("app.services.duels.bot_score", lambda *a, **k: -1)
    duel_id = duel_id_of(start_duel(client, "calculation"))

    assert client.get(f"/games/calculation?duel_id={duel_id}").status_code == 200
    response = client.post(f"/games/calculation/finish?duel_id={duel_id}")

    assert response.status_code == 200
    assert response.json()["duel"]["outcome"] == STATUS_WON


def test_reaction_duel_settles_on_the_last_round(client, db, monkeypatch):
    register_and_login(client, "quickdraw")
    monkeypatch.setattr("app.services.duels.bot_score", lambda *a, **k: 0)
    monkeypatch.setattr("app.routes.pages.generate_delay", lambda: 0.01)
    duel_id = duel_id_of(start_duel(client, "reaction"))

    # La page crée la partie côté serveur : sans elle, /wait n'a rien à attendre.
    assert client.get(f"/games/reaction?duel_id={duel_id}").status_code == 200

    final = None
    for _ in range(5):
        client.post("/games/reaction/wait")
        time.sleep(0.15)
        final = client.post(f"/games/reaction/click?duel_id={duel_id}").json()

    assert final["game_finished"] is True
    assert final["duel"]["outcome"] == STATUS_WON
    assert final["duel"]["player_score"] == final["final_score"]


def test_a_duel_settles_once(client, db):
    """Reglement en double : la prime de victoire serait fermee."""
    register_and_login(client, "once")
    user = get_user(db, "once")
    duel = Duel(
        user_id=user.id,
        game_type="memory",
        difficulty="regular",
        level=2,
        bot_name="Volt",
        bot_score=100,
        status=STATUS_PENDING,
        expires_at=utcnow() + timedelta(hours=1),
    )
    db.add(duel)
    db.commit()

    first = duels.settle_duel(db, duel, user, 250)
    assert first["outcome"] == STATUS_WON

    with pytest.raises(DuelError):
        duels.settle_duel(db, duel, user, 999_999)


def test_a_duel_cannot_be_replayed_to_farm_score(client, db, monkeypatch):
    """Le duel ne doit pas permettre de rejouer une partie déjà soldée.

    Le jeton de partie est à usage unique : le rejeu est refusé avant tout
    nouveau crédit de score.
    """
    register_and_login(client, "farmer")
    monkeypatch.setattr("app.services.duels.bot_score", lambda *a, **k: 0)
    duel_id = duel_id_of(start_duel(client, "memory"))

    play_memory(client, duel_id)
    after_first = get_user(db, "farmer").total_score

    assert (
        client.post(
            f"/games/memory/submit?answer=1234&duel_id={duel_id}"
        ).status_code
        == 400
    )
    assert get_user(db, "farmer").total_score == after_first


def test_duel_outcome_is_recorded(client, db, monkeypatch):
    register_and_login(client, "historian")
    monkeypatch.setattr("app.services.duels.bot_score", lambda *a, **k: 0)
    duel_id = duel_id_of(start_duel(client, "memory"))
    play_memory(client, duel_id)

    row = db.get(Duel, duel_id)

    assert row.status == STATUS_WON
    assert row.player_score > 0
    assert row.settled_at is not None


def test_duels_page_shows_the_record(client, db, monkeypatch):
    register_and_login(client, "recordist")
    monkeypatch.setattr("app.services.duels.bot_score", lambda *a, **k: 0)
    duel_id = duel_id_of(start_duel(client, "memory"))
    play_memory(client, duel_id)

    html = client.get("/duels").text

    assert "Won" in html
    assert "Memory" in html


# ---------------------------------------------------------------------------
# Limites
# ---------------------------------------------------------------------------


def test_an_expired_duel_is_not_playable(client, db):
    register_and_login(client, "slowpoke")
    duel_id = duel_id_of(start_duel(client, "memory"))
    row = db.get(Duel, duel_id)
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()

    response = client.get(f"/games/memory?duel_id={duel_id}", follow_redirects=False)

    assert response.status_code == 303
    assert db.get(Duel, duel_id).status == STATUS_EXPIRED


def test_a_duel_belongs_to_its_owner(client, db):
    owner = TestClient(client.app)
    register_and_login(owner, "owner")
    duel_id = duel_id_of(start_duel(owner, "memory"))

    thief = TestClient(client.app)
    register_and_login(thief, "thief")
    response = thief.get(f"/games/memory?duel_id={duel_id}", follow_redirects=False)

    assert response.status_code == 303
    assert db.get(Duel, duel_id).status == STATUS_PENDING


def test_a_duel_cannot_be_played_with_the_wrong_game(client, db):
    register_and_login(client, "switcher")
    duel_id = duel_id_of(start_duel(client, "memory"))

    response = client.get(
        f"/games/reaction?duel_id={duel_id}", follow_redirects=False
    )

    assert response.status_code == 303
    assert db.get(Duel, duel_id).status == STATUS_PENDING


def test_an_unknown_duel_id_is_refused(client):
    register_and_login(client, "ghost")

    assert (
        client.get("/games/memory?duel_id=4242", follow_redirects=False).status_code == 303
    )
