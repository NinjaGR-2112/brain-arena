"""Duel contre un bot.

Un duel est un habillage par-dessus une partie normale : le joueur joue
vraiment la partie, via les routes de jeu existantes, avec le même jeton à
usage unique et le même crédit de score et d'XP. Le duel n'ajoute que trois
choses : un adversaire, un **niveau interne** et une issue.

Le niveau est interne et **partagé** : le bot joue au même niveau que le
joueur, sans quoi le duel ne serait pas équitable. Il n'est jamais renvoyé au
client — c'est lui qui dose la force de l'adversaire, et le joueur n'a pas à
le connaître.

``bot_score`` est tiré **une seule fois**, au lancement : le bot ne rejoue
jamais en fonction de ce que fait le joueur.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.user import User
from app.utils.time import utcnow

STATUS_PENDING = "pending"
STATUS_WON = "won"
STATUS_LOST = "lost"
STATUS_DRAWN = "drawn"
STATUS_EXPIRED = "expired"

# Issues possibles d'un duel réglé. « expired » n'est pas une défaite : la
# partie n'a simplement jamais été finie.
OUTCOMES = (STATUS_WON, STATUS_LOST, STATUS_DRAWN)


class Duel(Base):
    __tablename__ = "duels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    game_type: Mapped[str] = mapped_column(String(20))

    # Force de l'adversaire, jamais exposée au client.
    difficulty: Mapped[str] = mapped_column(String(10))

    # Niveau interne, partagé par le joueur et le bot.
    level: Mapped[int] = mapped_column(Integer)

    bot_name: Mapped[str] = mapped_column(String(50))
    bot_score: Mapped[int] = mapped_column(Integer)

    player_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default=STATUS_PENDING, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        # Toutes les lectures portent sur les duels d'un joueur, par statut.
        Index("ix_duels_user_status", "user_id", "status"),
    )
