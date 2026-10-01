"""create friendships table

Revision ID: e7235fc5ccd9
Revises: 2603988de3bc
Create Date: 2026-10-01 20:20:40.286487

Une ligne par couple de joueurs, orientée (``requester_id`` a invité
``addressee_id``). La contrainte d'unicité sur le couple interdit les doublons
et les invitations dans les deux sens en parallèle ; les index portent sur
l'« autre bout » de la relation, seule façon dont le service la lit.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7235fc5ccd9"
down_revision: Union[str, Sequence[str], None] = "2603988de3bc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "friendships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("addressee_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["addressee_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("requester_id", "addressee_id", name="uq_friendships_pair"),
    )
    op.create_index(
        op.f("ix_friendships_requester_id"), "friendships", ["requester_id"], unique=False
    )
    op.create_index(
        op.f("ix_friendships_addressee_id"), "friendships", ["addressee_id"], unique=False
    )
    op.create_index(
        "ix_friendships_addressee_status",
        "friendships",
        ["addressee_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_friendships_addressee_status", table_name="friendships")
    op.drop_index(op.f("ix_friendships_addressee_id"), table_name="friendships")
    op.drop_index(op.f("ix_friendships_requester_id"), table_name="friendships")
    op.drop_table("friendships")
