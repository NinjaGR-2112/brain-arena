"""Partie de jeu en cours, stockée côté serveur.

Avant cette table, l'état sensible d'une partie (séquence Memory, réponse
Calculation, instant du signal Reaction) vivait dans le cookie de session
Starlette. Ce cookie est **signé** mais pas chiffré : il est donc lisible en
base64 par le client, et surtout **rejouable** — renvoyer un ancien cookie
créditait une nouvelle partie et son XP.

La table ``game_sessions`` corrige les deux problèmes :

- le client ne reçoit qu'un **jeton opaque** (aléatoire, 16 octets) ;
- l'état réel reste en base, donc jamais lisible ni modifiable ;
- une partie est **consommée** dès soumission (``status`` passe à
  ``consumed``) : un rejeu du même jeton est refusé ;
- le jeton est lié à ``user_id``, donc inutilisable par un autre compte ;
- ``expires_at`` borne la durée de vie d'une partie abandonnée.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.utils.time import utcnow

STATUS_ACTIVE = "active"
STATUS_CONSUMED = "consumed"


class GameSession(Base):
    __tablename__ = "game_sessions"

    # Jeton opaque remis au client. Aléatoire, jamais devinable.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    game_type: Mapped[str] = mapped_column(String(20))
    # Niveau validé côté serveur : celui demandé par le client est borné.
    level: Mapped[int] = mapped_column(Integer, default=1)

    # État du jeu, sérialisé en JSON. Son contenu dépend de game_type.
    state: Mapped[str] = mapped_column(Text, default="{}")

    status: Mapped[str] = mapped_column(String(10), default=STATUS_ACTIVE)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_game_sessions_user_status", "user_id", "status"),
    )
