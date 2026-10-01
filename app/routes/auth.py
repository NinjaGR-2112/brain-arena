from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.security import dummy_verify, hash_password, verify_password
from app.database.session import get_db
from app.models.user import User
from app.schemas.user import UserLogin, UserRegister

router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    existing = db.execute(
        select(User).where(
            (User.username == user_data.username) | (User.email == user_data.email)
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"id": new_user.id, "username": new_user.username}


@router.post("/login")
def login(user_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    user = db.execute(
        select(User).where(User.username == user_data.username)
    ).scalar_one_or_none()

    if not user:
        # Même message d'erreur que ci-dessous (pas d'énumération de comptes),
        # et même coût en temps : sans ce hachage factice, ce chemin répondait
        # en ~4 ms contre ~231 ms pour un compte existant.
        dummy_verify(user_data.password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    request.session["user_id"] = user.id

    return {"id": user.id, "username": user.username}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "xp": current_user.xp}


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out"}
