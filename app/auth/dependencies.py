"""Dépendances d'authentification réutilisables.

Deux variantes, selon le type de route :

- :func:`get_current_user` lève une erreur JSON — pour les routes d'API ;
- :func:`get_current_user_or_redirect` renvoie une redirection — pour les
  pages HTML, qui doivent ramener l'utilisateur vers ``/login`` plutôt que
  de lui afficher une erreur JSON.
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User

LOGIN_URL = "/login"


def _find_user(db: Session, user_id: int | None) -> User | None:
    if not user_id:
        return None
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Pour les routes d'API : renvoie l'utilisateur ou une erreur 401 JSON."""
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user = _find_user(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def get_current_user_or_redirect(request: Request, db: Session = Depends(get_db)):
    """Pour les pages HTML : renvoie l'utilisateur ou une redirection vers /login.

    Le code appelant doit tester ``isinstance(result, RedirectResponse)`` et
    renvoyer la redirection le cas échéant.
    """
    user = _find_user(db, request.session.get("user_id"))

    if user is None:
        return RedirectResponse(url=LOGIN_URL, status_code=status.HTTP_303_SEE_OTHER)

    return user
