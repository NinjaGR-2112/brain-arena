"""add player_id to users

Revision ID: 2603988de3bc
Revises: 856feda10561
Create Date: 2026-10-01 20:20:39.997397

Les comptes déjà en base reçoivent un identifiant généré : la colonne est
ajoutée nullable, remplie, puis passée en NOT NULL. Sans ce remplissage
préalable, la bascule échouerait sur les lignes existantes.

La génération est recopiée ici plutôt qu'importée depuis
``app/services/player_ids.py`` : une migration doit rester reproductible
telle quelle, même si le service évolue plus tard.
"""
from typing import Sequence, Union

import secrets

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2603988de3bc"
down_revision: Union[str, Sequence[str], None] = "856feda10561"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Alphabet sans caractères ambigus (pas de 0/O, 1/I/L/O/U).
ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
LENGTH = 8

# Table allégée, pour les mises à jour ligne à ligne sans dépendre des modèles.
users = sa.table(
    "users",
    sa.column("id", sa.Integer),
    sa.column("player_id", sa.String),
)


def _generate_player_id() -> str:
    chars = [secrets.choice(ALPHABET) for _ in range(LENGTH)]
    half = LENGTH // 2
    return "".join(chars[:half]) + "-" + "".join(chars[half:])


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("player_id", sa.String(length=9), nullable=True))
    op.create_index(op.f("ix_users_player_id"), "users", ["player_id"], unique=True)

    bind = op.get_bind()

    taken = {
        row[0]
        for row in bind.execute(
            sa.select(users.c.player_id).where(users.c.player_id.is_not(None))
        )
    }

    user_ids = [row[0] for row in bind.execute(sa.select(users.c.id))]

    for user_id in user_ids:
        # Collision improbable (10^-9 par tirage), mais l'index unique est là :
        # autant ne pas lui laisser l'occasion de refuser l'insertion.
        while True:
            candidate = _generate_player_id()
            if candidate not in taken:
                taken.add(candidate)
                break

        bind.execute(
            users.update().where(users.c.id == user_id).values(player_id=candidate)
        )

    # SQLite ne connaît pas ALTER COLUMN : le mode batch recrée la table.
    # Sur PostgreSQL, la même opération devient un ALTER TABLE ... SET NOT NULL.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "player_id", existing_type=sa.String(length=9), nullable=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_users_player_id"), table_name="users")
    op.drop_column("users", "player_id")
