"""Règles métier des duels.

Tout passe par ce module : les routes traduisent une demande HTTP en appel de
service, et une :class:`DuelError` en message affiché. Les règles sont donc
testables sans HTTP, et écrites une seule fois.

Pas de prime d'XP ici : le joueur marque exactement ce que marque sa partie.
Le duel change l'adversaire, pas l'économie du jeu.
"""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.duel import (
    STATUS_DRAWN,
    STATUS_EXPIRED,
    STATUS_LOST,
    STATUS_PENDING,
    STATUS_WON,
    Duel,
)
from app.models.user import User
from app.services.bots import bot_score, duel_level, pick_difficulty
from app.utils.time import utcnow

# Un duel doit être fini dans ce délai. Au-delà, il est abandonné : sans
# cette borne, une partie jamais terminée resterait « en attente » pour
# toujours et encombrerait la liste du joueur.
DUEL_TTL_SECONDS = 1800

GAME_TYPES = ("memory", "reaction", "calculation")

# Noms d'adversaires. La difficulté reste interne : le nom est décoratif.
BOT_NAMES = ("Volt", "Nibble", "Cortex", "Synapse", "Quark", "Pulse", "Logic")


class DuelError(Exception):
    """Règle métier violée. Le message est destiné au joueur."""


def start_duel(db: Session, user: User, game_type: str) -> Duel:
    """Crée un duel : difficulté dosee sur l'XP, score du bot tiré d'avance."""
    if game_type not in GAME_TYPES:
        raise DuelError("Unknown game")

    difficulty = pick_difficulty(user.xp)
    duel = Duel(
        user_id=user.id,
        game_type=game_type,
        difficulty=difficulty,
        level=duel_level(game_type, difficulty),
        bot_name=BOT_NAMES[user.id % len(BOT_NAMES)],
        bot_score=bot_score(game_type, difficulty),
        status=STATUS_PENDING,
        expires_at=utcnow() + timedelta(seconds=DUEL_TTL_SECONDS),
    )
    db.add(duel)
    db.commit()
    db.refresh(duel)
    return duel


def get_pending_duel(
    db: Session, duel_id: int | None, user_id: int, game_type: str
) -> Duel | None:
    """Renvoie le duel s'il est jouable, ``None`` sinon.

    Un duel n'est jouable que s'il appartient au joueur, concerne le bon jeu,
    est encore en attente et n'a pas expiré. Un duel expiré est soldé en
    « expired » au passage : la liste du joueur reste honnête sans cron de
    nettoyage.
    """
    if duel_id is None:
        return None

    duel = db.get(Duel, duel_id)

    if duel is None or duel.user_id != user_id or duel.game_type != game_type:
        return None
    if duel.status != STATUS_PENDING:
        return None

    if duel.expires_at <= utcnow():
        duel.status = STATUS_EXPIRED
        duel.settled_at = utcnow()
        db.commit()
        return None

    return duel


def settle_duel(db: Session, duel: Duel, user: User, player_score: int) -> dict:
    """Compare les scores et enregistre l'issue.

    Le règlement est refusé si le duel n'est plus en attente : sans ce garde,
    rejouer un identifiant de duel already règle la partie deux fois.
    """
    if duel.status != STATUS_PENDING:
        raise DuelError("Duel already settled")

    if duel.expires_at <= utcnow():
        duel.status = STATUS_EXPIRED
        duel.settled_at = utcnow()
        db.commit()
        raise DuelError("Duel expired")

    duel.player_score = player_score

    if player_score > duel.bot_score:
        duel.status = STATUS_WON
    elif player_score < duel.bot_score:
        duel.status = STATUS_LOST
    else:
        duel.status = STATUS_DRAWN

    duel.settled_at = utcnow()
    db.commit()
    db.refresh(duel)

    return {
        "outcome": duel.status,
        "bot_name": duel.bot_name,
        "bot_score": duel.bot_score,
        "player_score": duel.player_score,
    }


# ---------------------------------------------------------------------------
# Lectures pour la page de liste
# ---------------------------------------------------------------------------


def list_recent_duels(db: Session, user_id: int, limit: int = 10) -> list[Duel]:
    return (
        db.execute(
            select(Duel)
            .where(Duel.user_id == user_id)
            .order_by(Duel.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def record(db: Session, user_id: int) -> dict:
    """Bilan du joueur, tous jeux confondus."""
    rows = db.execute(select(Duel.status).where(Duel.user_id == user_id)).scalars().all()

    return {
        "won": rows.count(STATUS_WON),
        "lost": rows.count(STATUS_LOST),
        "drawn": rows.count(STATUS_DRAWN),
        "pending": rows.count(STATUS_PENDING),
    }
