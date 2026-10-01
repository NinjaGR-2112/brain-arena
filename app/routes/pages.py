"""Routes des pages et des jeux.

Règle de sécurité appliquée ici : **aucun état sensible ne transite par le
client**. Le client reçoit un jeton opaque, et l'état réel de la partie
(séquence, bonne réponse, instant du signal, compteur) vit dans la table
``game_sessions``. Les scores sont recalculés côté serveur, et chaque partie
n'est comptabilisée qu'une fois.
"""
import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_or_redirect
from app.database.session import get_db
from app.games.calculation import (
    CALCULATION_DURATION,
    FINISH_GRACE_SECONDS,
    LEVELS as CALCULATION_LEVELS,
    MAX_CORRECT_ANSWERS,
    MIN_ANSWER_INTERVAL_SECONDS,
    calculate_score as calculate_calculation_score,
    generate_operation,
    public_operation,
)
from app.games.levels import clamp_level
from app.games.memory import (
    ANSWER_WINDOW_SECONDS,
    LEVELS as MEMORY_LEVELS,
    generate_sequence,
)
from app.games.reaction import (
    GAME_TTL_SECONDS as REACTION_GAME_TTL,
    ROUND_WINDOW_SECONDS as REACTION_ROUND_WINDOW,
    TOTAL_ROUNDS,
    generate_delay,
    score_reaction_round,
)
from app.models.game_result import GameResult
from app.models.user import User
from app.services.game_sessions import (
    consume_game_session,
    create_game_session,
    extend_lifetime,
    get_active_game_session,
    load_state,
    save_state,
)
from app.services.scoring import calculate_memory_score
from app.utils.time import utcnow

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

NO_ACTIVE_GAME = "No active game session"


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, current_user=Depends(get_current_user_or_redirect)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": current_user},
    )


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


@router.get("/games/memory", response_class=HTMLResponse)
def memory_game(
    request: Request,
    level: int = 1,
    current_user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    level = clamp_level(level, MEMORY_LEVELS)
    sequence = generate_sequence(level)

    # La séquence va en base, pas dans le cookie : elle était lisible en
    # base64 depuis le navigateur.
    request.session["game_token"] = create_game_session(
        db,
        user_id=current_user.id,
        game_type="memory",
        level=level,
        state={"sequence": sequence},
        ttl_seconds=ANSWER_WINDOW_SECONDS,
    )

    return templates.TemplateResponse(
        request=request,
        name="memory.html",
        context={"sequence": sequence, "level": level},
    )


@router.post("/games/memory/submit")
def memory_submit(
    request: Request,
    answer: str,
    current_user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    game = get_active_game_session(
        db, token=request.session.get("game_token"), user_id=current_user.id, game_type="memory"
    )
    if game is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=NO_ACTIVE_GAME)

    state = load_state(game)
    time_taken = (utcnow() - game.created_at).total_seconds()

    answer_list = [int(digit) for digit in answer if digit.isdigit()]
    correct = answer_list == state["sequence"]

    score, xp = calculate_memory_score(game.level, correct, time_taken)

    # La partie est close avant d'être créditée : un rejeu du même jeton
    # échoue désormais sur get_active_game_session().
    consume_game_session(db, game)

    db.add(
        GameResult(
            user_id=current_user.id,
            game_type="memory",
            score=score,
            xp_earned=xp,
            duration=time_taken,
        )
    )
    current_user.xp += xp
    current_user.total_score += score
    current_user.games_played += 1
    db.commit()

    return {"correct": correct, "score": score, "xp_earned": xp, "time_taken": round(time_taken, 2)}


# ---------------------------------------------------------------------------
# Reaction
# ---------------------------------------------------------------------------


@router.get("/games/reaction", response_class=HTMLResponse)
def reaction_game(
    request: Request,
    current_user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    request.session["game_token"] = create_game_session(
        db,
        user_id=current_user.id,
        game_type="reaction",
        level=1,
        state={"round": 0, "scores": [], "signal_at": None},
        ttl_seconds=REACTION_GAME_TTL,
    )

    return templates.TemplateResponse(
        request=request,
        name="reaction.html",
        context={"total_rounds": TOTAL_ROUNDS},
    )


@router.post("/games/reaction/wait")
async def reaction_wait(
    request: Request,
    current_user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    game = get_active_game_session(
        db, token=request.session.get("game_token"), user_id=current_user.id, game_type="reaction"
    )
    if game is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=NO_ACTIVE_GAME)

    # Le délai reste côté serveur : la réponse HTTP n'arrive qu'au moment du
    # signal, le client ne peut donc pas connaître l'instant à l'avance.
    await asyncio.sleep(generate_delay())

    # Rechargement après l'attente : la partie a pu expirer ou être close.
    game = get_active_game_session(
        db, token=request.session.get("game_token"), user_id=current_user.id, game_type="reaction"
    )
    if game is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=NO_ACTIVE_GAME)

    state = load_state(game)
    state["signal_at"] = utcnow().isoformat()
    save_state(db, game, state)
    extend_lifetime(db, game, ttl_seconds=REACTION_ROUND_WINDOW)

    return {"signal": True}


@router.post("/games/reaction/click")
def reaction_click(
    request: Request,
    current_user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    game = get_active_game_session(
        db, token=request.session.get("game_token"), user_id=current_user.id, game_type="reaction"
    )
    if game is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=NO_ACTIVE_GAME)

    state = load_state(game)
    if not state.get("signal_at"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No signal was sent")

    signal_at = datetime.fromisoformat(state["signal_at"])
    reaction_time_ms = (utcnow() - signal_at).total_seconds() * 1000

    # Le signal est consommé : un second clic sans nouveau /wait est refusé.
    state["signal_at"] = None

    round_score, too_fast = score_reaction_round(reaction_time_ms)
    state["scores"].append(round_score)
    state["round"] += 1
    save_state(db, game, state)

    round_number = state["round"]
    scores = state["scores"]
    game_finished = round_number >= TOTAL_ROUNDS
    final_score = None
    xp_earned = None

    if game_finished:
        final_score = sum(scores) // len(scores)
        xp_earned = final_score // 10

        consume_game_session(db, game)

        db.add(
            GameResult(
                user_id=current_user.id,
                game_type="reaction",
                score=final_score,
                xp_earned=xp_earned,
                duration=0,
            )
        )
        current_user.xp += xp_earned
        current_user.total_score += final_score
        current_user.games_played += 1
        db.commit()

    return {
        "reaction_time_ms": round(reaction_time_ms, 1),
        "round_score": round_score,
        "too_fast": too_fast,
        "round_number": round_number,
        "game_finished": game_finished,
        "final_score": final_score,
        "xp_earned": xp_earned,
    }


# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------


@router.get("/games/calculation", response_class=HTMLResponse)
def calculation_game(
    request: Request,
    level: int = 1,
    current_user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    level = clamp_level(level, CALCULATION_LEVELS)
    operation = generate_operation(level)

    # La bonne réponse ne quitte pas le serveur ; le minuteur non plus : c'est
    # l'expiration de la partie qui borne les 30 secondes.
    request.session["game_token"] = create_game_session(
        db,
        user_id=current_user.id,
        game_type="calculation",
        level=level,
        state={"answer": operation["answer"], "correct_count": 0, "last_answer_at": None},
        ttl_seconds=CALCULATION_DURATION + FINISH_GRACE_SECONDS,
    )

    return templates.TemplateResponse(
        request=request,
        name="calculation.html",
        context={
            "operation": public_operation(operation),
            "level": level,
            "duration": CALCULATION_DURATION,
        },
    )


@router.post("/games/calculation/answer")
def calculation_answer(
    request: Request,
    value: int,
    current_user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    game = get_active_game_session(
        db, token=request.session.get("game_token"), user_id=current_user.id, game_type="calculation"
    )
    if game is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=NO_ACTIVE_GAME)

    state = load_state(game)
    now = utcnow()

    last_answer_at = state.get("last_answer_at")
    too_fast = (
        last_answer_at is not None
        and (now - datetime.fromisoformat(last_answer_at)).total_seconds()
        < MIN_ANSWER_INTERVAL_SECONDS
    )

    correct = False
    if not too_fast:
        correct = value == state["answer"]
        if correct:
            state["correct_count"] = min(state["correct_count"] + 1, MAX_CORRECT_ANSWERS)
        state["last_answer_at"] = now.isoformat()

    next_operation = generate_operation(game.level)
    state["answer"] = next_operation["answer"]
    save_state(db, game, state)

    return {
        "correct": correct,
        "too_fast": too_fast,
        "correct_count": state["correct_count"],
        "next_operation": public_operation(next_operation),
    }


@router.post("/games/calculation/finish")
def calculation_finish(
    request: Request,
    current_user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    # Sans partie active, plus de crédit : cet appel créait auparavant une
    # partie complète (score 0) et incrémentait games_played à chaque requête.
    game = get_active_game_session(
        db, token=request.session.get("game_token"), user_id=current_user.id, game_type="calculation"
    )
    if game is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=NO_ACTIVE_GAME)

    correct_count = load_state(game)["correct_count"]
    score, xp = calculate_calculation_score(correct_count, game.level)

    consume_game_session(db, game)

    db.add(
        GameResult(
            user_id=current_user.id,
            game_type="calculation",
            score=score,
            xp_earned=xp,
            duration=CALCULATION_DURATION,
        )
    )
    current_user.xp += xp
    current_user.total_score += score
    current_user.games_played += 1
    db.commit()

    return {"correct_count": correct_count, "score": score, "xp_earned": xp}


# ---------------------------------------------------------------------------
# Leaderboard et pages publiques
# ---------------------------------------------------------------------------


@router.get("/leaderboard", response_class=HTMLResponse)
def leaderboard(
    request: Request,
    page: int = Query(1, ge=1),
    current_user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    per_page = 20
    offset = (page - 1) * per_page

    users = db.execute(
        select(User).order_by(desc(User.xp)).offset(offset).limit(per_page)
    ).scalars().all()

    all_ranked = db.execute(select(User.id).order_by(desc(User.xp))).scalars().all()
    your_rank = all_ranked.index(current_user.id) + 1 if current_user.id in all_ranked else None

    return templates.TemplateResponse(
        request=request,
        name="leaderboard.html",
        context={
            "users": users,
            "page": page,
            "your_rank": your_rank,
            "start_rank": offset + 1,
            "total_pages": max(1, -(-len(all_ranked) // per_page)),
        },
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={})


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html", context={})
