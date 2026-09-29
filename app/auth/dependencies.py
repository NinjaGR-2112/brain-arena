from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.session import get_db
from app.models.user import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user

from fastapi.responses import RedirectResponse
from fastapi import status as http_status


def get_current_user_or_redirect(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")

    if not user_id:
        return RedirectResponse(url="/login", status_code=http_status.HTTP_303_SEE_OTHER)

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()

    if not user:
        return RedirectResponse(url="/login", status_code=http_status.HTTP_303_SEE_OTHER)

    return user