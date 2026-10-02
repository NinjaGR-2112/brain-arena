"""Identifiant joueur : court, lisible, unique.

Pourquoi pas le nom d'utilisateur : il est devinable (et changerait si un jour
on laisse le renommer), et deux joueurs ne doivent pas pouvoir être confondus.
Pourquoi pas l'e-mail : c'est une donnée personnelle, elle ne s'échange pas.

L'identifiant est donc une chaîne courte, sans caractères ambigus — pas de
``0``/``O``, pas de ``1``/``I``/``L``, pas de ``U`` (majuscule trop proche du
``V`` et source de gros mots involontaires) — groupée 4 + 4 pour rester
dicitable et recopiable à la main.
"""
import re
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User

# 30 symboles : 8 chiffres + 22 lettres. 30^8 ≈ 6,6 × 10^11 possibilités.
# L'alphabet exclut I, L, O et U (trop proches d'autres caractères) : un ID se
# dicte au téléphone ou se recopie à la main.
PLAYER_ID_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"

# Longueur de la partie aléatoire, hors tiret de séparation.
PLAYER_ID_LENGTH = 8

# Groupe de 4, tiret, groupe de 4 : « K7QM-2X9B ».
PLAYER_ID_PATTERN = re.compile(
    r"^[" + PLAYER_ID_ALPHABET + r"]{4}-[" + PLAYER_ID_ALPHABET + r"]{4}$"
)

# Nombre d'essais avant d'abandonner. La probabilité de collision est de
# l'ordre de 10^-9 pour quelques milliers de joueurs : boucler dix fois est
# déjà très large, et mieux vaut échouer bruyamment que dupliquer un ID.
MAX_GENERATION_ATTEMPTS = 10


def generate_player_id() -> str:
    """Tire un identifiant au hasard, au format ``ABCD-2345``."""
    chars = [secrets.choice(PLAYER_ID_ALPHABET) for _ in range(PLAYER_ID_LENGTH)]
    half = PLAYER_ID_LENGTH // 2
    return "".join(chars[:half]) + "-" + "".join(chars[half:])


def is_valid_player_id(value: str) -> bool:
    return bool(PLAYER_ID_PATTERN.fullmatch(value))


def normalize_player_id(raw: str) -> str | None:
    """Met en forme une saisie de joueur, ou renvoie ``None`` si elle est vide.

    Un ID se recopie à la main : il est donc normal d'accepter les minuscules,
    les espaces qui traînent et le tiret oublié. Tout ce qui ne redonne pas un
    ID valide est refusé ici, en un seul endroit.
    """
    compact = "".join(str(raw).upper().split())

    if len(compact) == PLAYER_ID_LENGTH:
        # Tiret oublié : « abcd2345 » -> « ABCD-2345 ».
        half = PLAYER_ID_LENGTH // 2
        compact = compact[:half] + "-" + compact[half:]

    return compact if is_valid_player_id(compact) else None


def generate_unique_player_id(db: Session, attempts: int = MAX_GENERATION_ATTEMPTS) -> str:
    """Identifiant garanti absent de la table ``users``.

    La contrainte d'unicité reste le dernier rempart : deux requêtes simultanées
    peuvent tirer le même ID entre le test et l'insertion. Dans ce cas
    l'insertion échoue sur la base, ce qui vaut mieux qu'un doublon silencieux.
    """
    for _ in range(attempts):
        candidate = generate_player_id()
        taken = db.execute(
            select(User.id).where(User.player_id == candidate)
        ).first()
        if taken is None:
            return candidate

    raise RuntimeError(
        f"Impossible de générer un identifiant joueur unique en {attempts} essais."
    )
