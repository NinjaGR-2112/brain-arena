"""Pages et actions liées aux amis.

Formulaire HTML + redirection : pas de JavaScript nécessaire pour ajouter,
accepter ou retirer un ami. Les messages de résultat transitent par la session
(« flash ») : une redirection ne peut pas transporter de contexte, et le cookie
de session est déjà signé par le projet.
"""
from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_or_redirect
from app.database.session import get_db
from app.services import friendships
from app.services.friendships import FriendshipError

router = APIRouter(prefix="/friends", tags=["friends"])
templates = Jinja2Templates(directory="app/templates")

FLASH_KEY = "flash"


def _render(
    request: Request,
    user,
    db: Session,
    *,
    error: str | None = None,
    status_code: int = status.HTTP_200_OK,
):
    """Affiche la page des amis, avec son éventuel message d'erreur."""
    # Le message d'une redirection précédente n'est lu qu'une fois.
    message = request.session.pop(FLASH_KEY, None)

    return templates.TemplateResponse(
        request=request,
        name="friends.html",
        status_code=status_code,
        context={
            "user": user,
            "friends": friendships.list_friends(db, user.id),
            "incoming": friendships.list_incoming_requests(db, user.id),
            "outgoing": friendships.list_outgoing_requests(db, user.id),
            "error": error,
            "message": message,
        },
    )


@router.get("", response_class=HTMLResponse)
def friends_page(
    request: Request,
    current_user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    return _render(request, current_user, db)


@router.post("/request")
def send_friend_request(
    request: Request,
    player_id: str = Form(...),
    current_user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    try:
        friendships.send_request(db, current_user.id, player_id)
    except FriendshipError as exc:
        # Erreur métier : la page est réaffichée telle quelle, en 400.
        return _render(request, current_user, db, error=str(exc), status_code=400)

    request.session[FLASH_KEY] = "Friend request sent."
    return RedirectResponse(url="/friends", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{friendship_id}/accept")
def accept_friend_request(
    request: Request,
    friendship_id: int,
    current_user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    try:
        friendships.accept_request(db, friendship_id, current_user.id)
    except FriendshipError as exc:
        return _render(request, current_user, db, error=str(exc), status_code=400)

    request.session[FLASH_KEY] = "Friend added."
    return RedirectResponse(url="/friends", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{friendship_id}/remove")
def remove_friendship(
    request: Request,
    friendship_id: int,
    current_user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    try:
        friendships.remove_friendship(db, friendship_id, current_user.id)
    except FriendshipError as exc:
        return _render(request, current_user, db, error=str(exc), status_code=400)

    request.session[FLASH_KEY] = "Done."
    return RedirectResponse(url="/friends", status_code=status.HTTP_303_SEE_OTHER)
