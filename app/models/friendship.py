"""Relation entre deux joueurs.

Une seule ligne par couple, orientée : ``requester_id`` a invité
``addressee_id``. Le statut porte l'état de la relation :

- ``pending``  : demande en attente, seul le destinataire peut répondre ;
- ``accepted`` : les deux sont amis ;
- ``declined`` : le destinataire a refusé ;
- ``removed``  : l'un des deux a retiré l'autre.

Les états terminaux ne suppriment pas la ligne : une nouvelle demande la
réactive. Cela évite de dupliquer l'historique d'un même couple et de se
heurter à la contrainte d'unicité ``(requester_id, addressee_id)``.

``responded_at`` n'est renseigné qu'une fois la demande traitée : il permet de
trier les demandes reçues et de mesurer un délai de réponse.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.user import User
from app.utils.time import utcnow

STATUS_PENDING = "pending"
STATUS_ACCEPTED = "accepted"
STATUS_DECLINED = "declined"
STATUS_REMOVED = "removed"

STATUSES = (STATUS_PENDING, STATUS_ACCEPTED, STATUS_DECLINED, STATUS_REMOVED)


class Friendship(Base):
    __tablename__ = "friendships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Deux clés vers ``users`` : SQLAlchemy a besoin de ``foreign_keys`` pour
    # savoir laquelle des deux porte chaque relation.
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    addressee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    requester: Mapped[User] = relationship("User", foreign_keys=[requester_id])
    addressee: Mapped[User] = relationship("User", foreign_keys=[addressee_id])

    status: Mapped[str] = mapped_column(String(10), default=STATUS_PENDING, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friendships_pair"),
        # Toutes les lectures du service portent sur « l'autre bout » du couple.
        Index("ix_friendships_addressee_status", "addressee_id", "status"),
    )

    def other_party(self, user_id: int) -> User:
        """L'autre joueur de la relation, quel que soit le sens de la ligne."""
        return self.addressee if self.requester_id == user_id else self.requester
