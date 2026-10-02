"""Pages et actions liées aux duels contre les bots.

Formulaire HTML + redirection, comme les amis : pas de JavaScript à ajouter.
La difficulté du bot n'apparaît jamais dans une page ni dans une réponse —
elle ne sert qu'à doser le niveau interne de la partie.
"""
from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_or_redirect
from app.database.session import get_db
from app.services import duels
from app.services.duels import DuelError

router = APIRouter(prefix="/duels", tags=["duels"])
templates = Jinja2Templates(directory="app/templates")

FLASH_KEY = "flash"

# Libellés affichés au joueur. La difficulté, elle, reste interne.
GAME_LABELS = {"memory": "Memory", "reaction": "Reaction", "calculation": "Calculation"}

OUTCOME_LABELS = {
    "won": "Won",
    "lost": "Lost",
    "drawn": "Draw",
    "expired": "Expired",
}


def _render(request: Request, user, db: Session, *, error=None, status_code=200):
    """Affiche la page des duels, avec son éventuel message d'erreur."""
    message = request.session.pop(FLASH_KEY, None)

    return templates.TemplateResponse(
        request=request,
        name="duels.html",
        status_code=status_code,
        context={
            "user": user,
            "recent": duels.list_recent_duels(db, user.id),
            "record": duels.record(db, user.id),
            "game_labels": GAME_LABELS,
            "outcome_labels": OUTCOME_LABELS,
            "error": error,
            "message": message,
        },
    )


def duel_or_redirect(db: Session, request: Request, duel_id, user, game_type: str):
    """Résout le paramètre ``duel`` d'une route de jeu.

    Renvoie ``(duel, redirect)`` : soit le duel jouable et pas de redirection,
    soit pas de duel et une redirection vers ``/duels``. Les routes de jeu
    n'ont ainsi que deux lignes à écrire, et un identifiant de duel périmé,
    étranger ou décalé sur le jeu ne peut jamais faire jouer une partie qui
    n'est pas la bonne.
    """
    if duel_id is None:
        return None, None

    duel = duels.get_pending_duel(db, duel_id, user.id, game_type)

    if duel is None:
        request.session[FLASH_KEY] = "This duel is no longer available."
        return None, RedirectResponse(url="/duels", status_code=status.HTTP_303_SEE_OTHER)

    return duel, None


def settle_duel_outcome(db: Session, duel, user, player_score: int) -> dict | None:
    """Règle le duel et renvoie son issue, ou ``None`` s'il est déjà soldé.

    Un duel déjà réglé ne fait pas échouer la partie du joueur : la partie a
    été jouée et créditée normalement, seule l'issue du duel manque.
    """
    if duel is None:
        return None

    try:
        return duels.settle_duel(db, duel, user, player_score)
    except DuelError:
        return None


@router.get("", response_class=HTMLResponse)
def duels_page(
    request: Request,
    current_user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    return _render(request, current_user, db)


@router.post("/start")
def start_duel(
    request: Request,
    game_type: str = Form(...),
    current_user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    try:
        duel = duels.start_duel(db, current_user, game_type)
    except DuelError as exc:
        return _render(request, current_user, db, error=str(exc), status_code=400)

    return RedirectResponse(
        url=f"/games/{duel.game_type}?duel_id={duel.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
