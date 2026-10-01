"""Cycle de vie des parties : création, lecture d'état, consommation.

Toutes les routes de jeu passent par ce module plutôt que par
``request.session``, afin qu'aucun état sensible ne transite par le client.
"""
import json
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.game_session import (
    STATUS_ACTIVE,
    STATUS_CONSUMED,
    GameSession,
)
from app.utils.time import utcnow

# 16 octets d'aléa -> 128 bits d'entropie, largement suffisant pour un jeton.
TOKEN_BYTES = 16


def create_game_session(
    db: Session,
    *,
    user_id: int,
    game_type: str,
    level: int,
    state: dict,
    ttl_seconds: int,
) -> str:
    """Crée une partie côté serveur et renvoie le jeton à transmettre au client."""
    now = utcnow()
    row = GameSession(
        id=secrets.token_urlsafe(TOKEN_BYTES),
        user_id=user_id,
        game_type=game_type,
        level=level,
        state=json.dumps(state),
        status=STATUS_ACTIVE,
        created_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    db.add(row)
    db.commit()
    return row.id


def get_active_game_session(
    db: Session,
    *,
    token: str | None,
    user_id: int,
    game_type: str,
) -> GameSession | None:
    """Renvoie la partie si le jeton est valide, appartient à l'utilisateur,
    est toujours actif et n'a pas expiré. ``None`` sinon.

    C'est cette fonction qui rend le rejeu inopérant : un jeton déjà consommé
    ou expiré ne correspond à aucune ligne.
    """
    if not token:
        return None

    return db.execute(
        select(GameSession).where(
            GameSession.id == token,
            GameSession.user_id == user_id,
            GameSession.game_type == game_type,
            GameSession.status == STATUS_ACTIVE,
            GameSession.expires_at > utcnow(),
        )
    ).scalar_one_or_none()


def load_state(row: GameSession) -> dict:
    """Déserialise l'état JSON d'une partie."""
    return json.loads(row.state) if row.state else {}


def save_state(db: Session, row: GameSession, state: dict) -> None:
    """Persiste un état modifié. Réassigner ``state`` marque l'objet comme modifié."""
    row.state = json.dumps(state)
    db.add(row)
    db.commit()


def extend_lifetime(db: Session, row: GameSession, *, ttl_seconds: int) -> None:
    """Repousse l'expiration (utilisé par Reaction pour dater chaque round)."""
    row.expires_at = utcnow() + timedelta(seconds=ttl_seconds)
    db.add(row)
    db.commit()


def consume_game_session(db: Session, row: GameSession) -> None:
    """Clôture définitivement une partie : le jeton ne peut plus être rejoué."""
    row.status = STATUS_CONSUMED
    row.state = "{}"
    db.add(row)
    db.commit()
