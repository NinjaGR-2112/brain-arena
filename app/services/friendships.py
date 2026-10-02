"""Règles métier des amis.

Tout passe par ce module : les routes ne font que traduire une demande HTTP en
appel de service, et une :class:`FriendshipError` en message affiché. Les
règles sont testées sans HTTP, et une seule fois.
"""
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.friendship import (
    STATUS_ACCEPTED,
    STATUS_DECLINED,
    STATUS_PENDING,
    STATUS_REMOVED,
    Friendship,
)
from app.models.user import User
from app.services.player_ids import normalize_player_id
from app.utils.time import utcnow


class FriendshipError(Exception):
    """Règle métier violée. Le message est destiné au joueur."""


def _find(db: Session, friendship_id: int) -> Friendship | None:
    return db.get(Friendship, friendship_id)


def _pair_exists(db: Session, first_id: int, second_id: int) -> Friendship | None:
    """La ligne du couple, dans un sens comme dans l'autre."""
    return db.execute(
        select(Friendship).where(
            or_(
                (Friendship.requester_id == first_id)
                & (Friendship.addressee_id == second_id),
                (Friendship.requester_id == second_id)
                & (Friendship.addressee_id == first_id),
            )
        )
    ).scalar_one_or_none()


def send_request(db: Session, requester_id: int, raw_player_id: str) -> Friendship:
    """Envoie (ou renvoie) une demande d'ami à partir d'un identifiant joueur."""
    player_id = normalize_player_id(raw_player_id)
    if player_id is None:
        raise FriendshipError("Invalid player ID")

    target = db.execute(
        select(User).where(User.player_id == player_id)
    ).scalar_one_or_none()
    if target is None:
        raise FriendshipError("No player with this ID")
    if target.id == requester_id:
        raise FriendshipError("You cannot add yourself")

    existing = _pair_exists(db, requester_id, target.id)

    if existing is not None and existing.status == STATUS_ACCEPTED:
        raise FriendshipError("You are already friends")

    if existing is not None and existing.status == STATUS_PENDING:
        if existing.requester_id == requester_id:
            raise FriendshipError("You already sent a request to this player")
        raise FriendshipError("This player already sent you a request")

    if existing is None:
        existing = Friendship(requester_id=requester_id, addressee_id=target.id)
        db.add(existing)

    # Nouvelle demande, ou demande qui réveille une ligne refusée / retirée.
    existing.status = STATUS_PENDING
    existing.responded_at = None
    db.commit()
    db.refresh(existing)
    return existing


def accept_request(db: Session, friendship_id: int, user_id: int) -> Friendship:
    """Accepte une demande revenue. Seul le destinataire peut accepter."""
    row = _find(db, friendship_id)

    if row is None or row.addressee_id != user_id:
        raise FriendshipError("Friend request not found")
    if row.status != STATUS_PENDING:
        raise FriendshipError("This request is no longer pending")

    row.status = STATUS_ACCEPTED
    row.responded_at = utcnow()
    db.commit()
    db.refresh(row)
    return row


def remove_friendship(db: Session, friendship_id: int, user_id: int) -> Friendship:
    """Refuse une demande reçue, ou retire un ami.

    Une seule action pour les deux cas : la ligne apparient à l'un des deux
    joueurs, et son état terminal diffère selon qu'une demande était en
    attente (``declined``) ou déjà acceptée (``removed``).
    """
    row = _find(db, friendship_id)

    if row is None or user_id not in (row.requester_id, row.addressee_id):
        raise FriendshipError("Friendship not found")

    if row.status == STATUS_PENDING:
        row.status = STATUS_DECLINED
    else:
        row.status = STATUS_REMOVED
    row.responded_at = utcnow()
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Lectures pour la page de liste
# ---------------------------------------------------------------------------


def _with_other_party(rows: list[Friendship], user_id: int) -> list[tuple[Friendship, User]]:
    return [(row, row.other_party(user_id)) for row in rows]


def list_friends(db: Session, user_id: int) -> list[tuple[Friendship, User]]:
    rows = db.execute(
        select(Friendship)
        .where(
            Friendship.status == STATUS_ACCEPTED,
            or_(
                Friendship.requester_id == user_id,
                Friendship.addressee_id == user_id,
            ),
        )
        .order_by(Friendship.responded_at.desc())
    ).scalars().all()
    return _with_other_party(rows, user_id)


def list_incoming_requests(db: Session, user_id: int) -> list[tuple[Friendship, User]]:
    rows = db.execute(
        select(Friendship)
        .where(
            Friendship.addressee_id == user_id,
            Friendship.status == STATUS_PENDING,
        )
        .order_by(Friendship.created_at.desc())
    ).scalars().all()
    return _with_other_party(rows, user_id)


def list_outgoing_requests(db: Session, user_id: int) -> list[tuple[Friendship, User]]:
    rows = db.execute(
        select(Friendship)
        .where(
            Friendship.requester_id == user_id,
            Friendship.status == STATUS_PENDING,
        )
        .order_by(Friendship.created_at.desc())
    ).scalars().all()
    return _with_other_party(rows, user_id)
