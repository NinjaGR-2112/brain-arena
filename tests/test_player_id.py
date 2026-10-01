"""Identifiant joueur : court, lisible, unique.

C'est la clé d'entrée du système d'amis : on ajoute un ami par identifiant,
pas par e-mail ni par nom d'utilisateur (dévinable, et changeable).
"""
from app.models.user import User
from app.services.player_ids import (
    PLAYER_ID_LENGTH,
    PLAYER_ID_PATTERN,
    generate_player_id,
    generate_unique_player_id,
    normalize_player_id,
)
from tests.helpers import register_and_login


def test_register_returns_a_player_id(client):
    register_and_login(client, "identified")

    data = client.get("/auth/me").json()

    assert PLAYER_ID_PATTERN.fullmatch(data["player_id"])


def test_player_ids_are_unique_across_users(client, db):
    for name in ("dup-one", "dup-two", "dup-three"):
        register_and_login(client, name)

    db.expire_all()
    ids = [user.player_id for user in db.query(User).all()]

    assert len(ids) == 3
    assert len(set(ids)) == 3


def test_generated_ids_respect_the_format():
    for _ in range(200):
        player_id = generate_player_id()

        assert len(player_id) == PLAYER_ID_LENGTH + 1  # + le tiret
        assert PLAYER_ID_PATTERN.fullmatch(player_id)


def test_generated_ids_avoid_ambiguous_characters():
    """Pas de 0/O ni de 1/I/L : un ID se dicte ou se recopie à la main."""
    for _ in range(200):
        player_id = generate_player_id()

        assert not set(player_id) & set("01ILOU")


def test_generate_unique_player_id_never_returns_a_taken_one(client, db):
    taken = {generate_player_id() for _ in range(50)}
    for index, player_id in enumerate(taken):
        db.add(
            User(
                username=f"taken{index}",
                email=f"taken{index}@example.com",
                password_hash="not-a-real-hash",
                player_id=player_id,
            )
        )
    db.commit()

    assert generate_unique_player_id(db) not in taken


def test_normalize_player_id_accepts_lowercase_and_missing_dash():
    assert normalize_player_id("abcd-2345") == "ABCD-2345"
    assert normalize_player_id(" abcd 2345 ") == "ABCD-2345"
    assert normalize_player_id("ABCD2345") == "ABCD-2345"


def test_normalize_player_id_rejects_garbage():
    for value in ("", "   ", "ABC", "ABCD-234", "ABCD-23456", "ABCD_2345", "ABCD-2345-6789"):
        assert normalize_player_id(value) is None


def test_player_id_is_displayed_on_the_dashboard(client):
    register_and_login(client, "showme")

    assert client.get("/auth/me").json()["player_id"] in client.get("/dashboard").text


def test_player_id_pattern_is_anchored():
    """Un motif non ancé laisserait passer « xABCD-2345 »."""
    assert PLAYER_ID_PATTERN.fullmatch("xABCD-2345") is None
    assert PLAYER_ID_PATTERN.fullmatch("ABCD-2345") is not None
