"""Hachage des mots de passe.

bcrypt est utilisé directement, sans Passlib : Passlib 1.7.4 (dernière
version publiée, non maintenue) est incompatible avec bcrypt 4.x/5.x.
"""
import bcrypt

# Limite structurelle de bcrypt : seules les 72 premiers octets du mot de
# passe sont hachés. Au-delà, bcrypt 5.0.0 lève une ``ValueError``
# ("password cannot be longer than 72 bytes"), qui remontait en HTTP 500
# à l'inscription comme à la connexion.
MAX_PASSWORD_BYTES = 72


class PasswordTooLongError(ValueError):
    """Mot de passe trop long pour être haché par bcrypt."""


def hash_password(plain_password: str) -> str:
    password_bytes = plain_password.encode("utf-8")

    if len(password_bytes) > MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(
            f"Le mot de passe dépasse {MAX_PASSWORD_BYTES} octets une fois "
            f"encodé en UTF-8 ({len(password_bytes)} octets)."
        )

    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode("utf-8")

    # Un mot de passe hors limite ne peut correspondre à aucun hachage
    # existant (il aurait été refusé à l'inscription). On renvoie False
    # plutôt que de laisser bcrypt lever une exception.
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        return False

    return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))


# Hachage factice, calculé paresseusement, pour égaliser le temps de réponse
# du login. Sans lui, un compte inexistant répondait en ~4 ms contre ~231 ms
# pour un compte existant : le message d'erreur était identique, mais le
# délai trahissait l'existence du compte.
_dummy_hash: str | None = None


def _get_dummy_hash() -> str:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt()).decode("utf-8")
    return _dummy_hash


def dummy_verify(plain_password: str) -> None:
    """Exécute un vrai travail bcrypt, résultat jeté.

    À appeler sur le chemin « utilisateur inconnu » pour qu'il coûte le même
    temps que le chemin « mot de passe incorrect ».
    """
    verify_password(plain_password, _get_dummy_hash())
