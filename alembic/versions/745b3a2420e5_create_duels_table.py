"""create duels table

Revision ID: 745b3a2420e5
Revises: e7235fc5ccd9
Create Date: 2026-10-01 21:12:44.118293

Un duel range l'issue d'une partie contre un bot. ``difficulty`` et ``level``
sont internes : ils dosent la force de l'adversaire et ne sont jamais renvoyés
au client. ``player_score`` reste nul jusqu'au règlement — une partie non
terminée n'a pas de score à comparer.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "745b3a2420e5"
down_revision: Union[str, Sequence[str], None] = "e7235fc5ccd9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "duels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_type", sa.String(length=20), nullable=False),
        sa.Column("difficulty", sa.String(length=10), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("bot_name", sa.String(length=50), nullable=False),
        sa.Column("bot_score", sa.Integer(), nullable=False),
        sa.Column("player_score", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_duels_user_id"), "duels", ["user_id"], unique=False)
    op.create_index(
        "ix_duels_user_status", "duels", ["user_id", "status"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_duels_user_status", table_name="duels")
    op.drop_index(op.f("ix_duels_user_id"), table_name="duels")
    op.drop_table("duels")
