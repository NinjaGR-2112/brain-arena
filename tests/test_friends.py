"""Amis : demande par identifiant, acceptation, refus, suppression.

Le modèle est explicite : une ligne ``friendships`` par couple de joueurs, avec
un statut. Pas de suppression au refus — la ligne reste et peut être réactivée
par une nouvelle demande, ce qui évite de dupliquer l'historique et de se
frire à la contrainte d'unicité.
"""
from fastapi.testclient import TestClient

from app.models.friendship import (
    STATUS_ACCEPTED,
    STATUS_DECLINED,
    STATUS_PENDING,
    Friendship,
)
from tests.helpers import register_and_login


def player_id_of(client):
    return client.get("/auth/me").json()["player_id"]


def two_players(app, first="alice", second="bob"):
    """Deux clients connectés, sur la même base de test."""
    alice = TestClient(app)
    register_and_login(alice, first)
    bob = TestClient(app)
    register_and_login(bob, second)
    return alice, bob


def single_friendship(db):
    db.expire_all()
    return db.query(Friendship).one()


def add_friend(client, target_id):
    """POST sans suivre la redirection : on veut voir le 303 lui-même."""
    return client.post(
        "/friends/request", data={"player_id": target_id}, follow_redirects=False
    )


# ---------------------------------------------------------------------------
# Page et accès
# ---------------------------------------------------------------------------


def test_friends_page_requires_login(client):
    assert client.get("/friends", follow_redirects=False).status_code == 303


def test_friends_page_shows_the_player_id(client):
    register_and_login(client, "showme")

    html = client.get("/friends").text

    assert player_id_of(client) in html
    assert "Add a friend" in html


# ---------------------------------------------------------------------------
# Demande
# ---------------------------------------------------------------------------


def test_add_friend_creates_a_pending_request(client, db):
    alice, bob = two_players(client.app)

    response = add_friend(alice, player_id_of(bob))

    assert response.status_code == 303
    row = single_friendship(db)
    assert row.status == STATUS_PENDING
    assert row.requester.username == "alice"
    assert row.addressee.username == "bob"


def test_player_id_input_is_normalized(client, db):
    alice, bob = two_players(client.app)

    response = add_friend(alice, player_id_of(bob).lower().replace("-", ""))

    assert response.status_code == 303
    assert single_friendship(db).status == STATUS_PENDING


def test_cannot_add_yourself(client, db):
    register_and_login(client, "lonely")

    response = add_friend(client, player_id_of(client))

    assert response.status_code == 400
    assert "yourself" in response.text
    assert db.query(Friendship).count() == 0


def test_unknown_player_id_is_refused(client, db):
    register_and_login(client, "hopeful")

    response = add_friend(client, "ZZZZ-9999")

    assert response.status_code == 400
    assert "No player" in response.text
    assert db.query(Friendship).count() == 0


def test_malformed_player_id_is_refused(client, db):
    register_and_login(client, "typo")

    response = add_friend(client, "not-an-id")

    assert response.status_code == 400
    assert "Invalid player ID" in response.text
    assert db.query(Friendship).count() == 0


def test_duplicate_request_is_refused(client, db):
    alice, bob = two_players(client.app)
    add_friend(alice, player_id_of(bob))

    response = add_friend(alice, player_id_of(bob))

    assert response.status_code == 400
    assert db.query(Friendship).count() == 1


def test_reverse_request_is_refused(client, db):
    """Alice a invité Bob ; Bob ne peut pas inviter Alice en parallèle."""
    alice, bob = two_players(client.app)
    add_friend(alice, player_id_of(bob))

    response = add_friend(bob, player_id_of(alice))

    assert response.status_code == 400
    assert db.query(Friendship).count() == 1


# ---------------------------------------------------------------------------
# Acceptation, refus, suppression
# ---------------------------------------------------------------------------


def test_accept_request_makes_both_players_friends(client, db):
    alice, bob = two_players(client.app)
    add_friend(alice, player_id_of(bob))
    friendship_id = single_friendship(db).id

    response = bob.post(f"/friends/{friendship_id}/accept", follow_redirects=False)

    assert response.status_code == 303
    row = single_friendship(db)
    assert row.status == STATUS_ACCEPTED
    assert row.responded_at is not None
    assert player_id_of(alice) in alice.get("/friends").text
    assert player_id_of(bob) in bob.get("/friends").text


def test_only_the_addressee_can_accept(client, db):
    alice, bob = two_players(client.app)
    add_friend(alice, player_id_of(bob))
    friendship_id = single_friendship(db).id

    intruder = TestClient(client.app)
    register_and_login(intruder, "intruder")
    response = intruder.post(f"/friends/{friendship_id}/accept")

    assert response.status_code == 400
    assert single_friendship(db).status == STATUS_PENDING


def test_declined_request_can_be_sent_again(client, db):
    alice, bob = two_players(client.app)
    add_friend(alice, player_id_of(bob))
    friendship_id = single_friendship(db).id

    assert bob.post(
        f"/friends/{friendship_id}/remove", follow_redirects=False
    ).status_code == 303
    assert single_friendship(db).status == STATUS_DECLINED

    assert add_friend(alice, player_id_of(bob)).status_code == 303
    assert single_friendship(db).status == STATUS_PENDING


def test_remove_friend_ends_the_friendship(client, db):
    alice, bob = two_players(client.app)
    add_friend(alice, player_id_of(bob))
    friendship_id = single_friendship(db).id
    bob.post(f"/friends/{friendship_id}/accept", follow_redirects=False)

    response = alice.post(f"/friends/{friendship_id}/remove", follow_redirects=False)

    assert response.status_code == 303
    assert single_friendship(db).status != STATUS_ACCEPTED
    assert player_id_of(bob) not in alice.get("/friends").text


def test_removed_friend_can_be_added_again(client, db):
    alice, bob = two_players(client.app)
    add_friend(alice, player_id_of(bob))
    friendship_id = single_friendship(db).id
    bob.post(f"/friends/{friendship_id}/accept", follow_redirects=False)
    alice.post(f"/friends/{friendship_id}/remove", follow_redirects=False)

    assert add_friend(bob, player_id_of(alice)).status_code == 303
    assert single_friendship(db).status == STATUS_PENDING


def test_a_stranger_cannot_remove_a_friendship(client, db):
    alice, bob = two_players(client.app)
    add_friend(alice, player_id_of(bob))
    friendship_id = single_friendship(db).id

    intruder = TestClient(client.app)
    register_and_login(intruder, "nosy")
    response = intruder.post(f"/friends/{friendship_id}/remove")

    assert response.status_code == 400
    assert single_friendship(db).status == STATUS_PENDING


def test_unknown_friendship_id_is_refused(client):
    register_and_login(client, "ghosthunter")

    assert client.post("/friends/4242/accept").status_code == 400
    assert client.post("/friends/4242/remove").status_code == 400


# ---------------------------------------------------------------------------
# La page de liste
# ---------------------------------------------------------------------------


def test_friends_page_separates_friends_and_requests(client, db):
    alice, bob = two_players(client.app)
    add_friend(alice, player_id_of(bob))

    bob_page = bob.get("/friends").text
    assert "Requests received" in bob_page
    assert "alice" in bob_page

    alice_page = alice.get("/friends").text
    assert "Requests sent" in alice_page
    assert "bob" in alice_page

    bob.post(f"/friends/{single_friendship(db).id}/accept")

    assert "alice" in bob.get("/friends").text
    assert "Friends" in bob.get("/friends").text
