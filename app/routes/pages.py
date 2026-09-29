import time
import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_or_redirect
from app.database.session import get_db
from app.models.game_result import GameResult
from app.models.user import User
from app.games.memory import generate_sequence
from app.games.reaction import generate_delay, calculate_round_score
from app.games.calculation import generate_operation, calculate_score
from app.services.scoring import calculate_memory_score

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

TOTAL_ROUNDS = 5
CALCULATION_DURATION = 30


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, current_user=Depends(get_current_user_or_redirect)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": current_user},
    )


@router.get("/games/memory", response_class=HTMLResponse)
def memory_game(request: Request, level: int = 1, current_user=Depends(get_current_user_or_redirect)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    sequence = generate_sequence(level)
    request.session["memory_sequence"] = sequence
    request.session["memory_level"] = level
    request.session["memory_start_time"] = time.time()

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

    expected_sequence = request.session.get("memory_sequence")
    level = request.session.get("memory_level", 1)
    start_time = request.session.get("memory_start_time")

    if expected_sequence is None or start_time is None:
        return {"error": "No active game session"}

    time_taken = time.time() - start_time
    answer_list = [int(d) for d in answer if d.isdigit()]
    correct = answer_list == expected_sequence

    score, xp = calculate_memory_score(level, correct, time_taken)

    request.session.pop("memory_sequence", None)
    request.session.pop("memory_level", None)
    request.session.pop("memory_start_time", None)

    result = GameResult(
        user_id=current_user.id,
        game_type="memory",
        score=score,
        xp_earned=xp,
        duration=time_taken,
    )
    db.add(result)

    current_user.xp += xp
    current_user.total_score += score
    current_user.games_played += 1

    db.commit()

    return {"correct": correct, "score": score, "xp_earned": xp, "time_taken": round(time_taken, 2)}


@router.get("/games/reaction", response_class=HTMLResponse)
def reaction_game(request: Request, current_user=Depends(get_current_user_or_redirect)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    request.session["reaction_round"] = 0
    request.session["reaction_scores"] = []

    return templates.TemplateResponse(
        request=request,
        name="reaction.html",
        context={"total_rounds": TOTAL_ROUNDS},
    )


@router.post("/games/reaction/wait")
async def reaction_wait(request: Request, current_user=Depends(get_current_user_or_redirect)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    delay = generate_delay()
    await asyncio.sleep(delay)

    signal_time = time.time()
    request.session["reaction_signal_time"] = signal_time

    return {"signal": True}


@router.post("/games/reaction/click")
def reaction_click(request: Request, current_user=Depends(get_current_user_or_redirect), db: Session = Depends(get_db)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    signal_time = request.session.get("reaction_signal_time")
    if signal_time is None:
        return {"error": "No signal was sent"}

    click_time = time.time()
    reaction_time_ms = (click_time - signal_time) * 1000

    round_score = calculate_round_score(reaction_time_ms)

    scores = request.session.get("reaction_scores", [])
    scores.append(round_score)
    request.session["reaction_scores"] = scores

    round_number = request.session.get("reaction_round", 0) + 1
    request.session["reaction_round"] = round_number

    request.session.pop("reaction_signal_time", None)

    game_finished = round_number >= TOTAL_ROUNDS
    final_score = None
    xp_earned = None

    if game_finished:
        final_score = sum(scores) // len(scores)
        xp_earned = final_score // 10

        result = GameResult(
            user_id=current_user.id,
            game_type="reaction",
            score=final_score,
            xp_earned=xp_earned,
            duration=0,
        )
        db.add(result)
        current_user.xp += xp_earned
        current_user.total_score += final_score
        current_user.games_played += 1
        db.commit()

        request.session.pop("reaction_round", None)
        request.session.pop("reaction_scores", None)

    return {
        "reaction_time_ms": round(reaction_time_ms, 1),
        "round_score": round_score,
        "round_number": round_number,
        "game_finished": game_finished,
        "final_score": final_score,
        "xp_earned": xp_earned,
    }


@router.get("/games/calculation", response_class=HTMLResponse)
def calculation_game(request: Request, level: int = 1, current_user=Depends(get_current_user_or_redirect)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    operation = generate_operation(level)
    request.session["calc_answer"] = operation["answer"]
    request.session["calc_level"] = level
    request.session["calc_correct_count"] = 0

    return templates.TemplateResponse(
        request=request,
        name="calculation.html",
        context={"operation": operation, "level": level, "duration": CALCULATION_DURATION},
    )


@router.post("/games/calculation/answer")
def calculation_answer(request: Request, value: int, current_user=Depends(get_current_user_or_redirect)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    expected = request.session.get("calc_answer")
    level = request.session.get("calc_level", 1)
    correct_count = request.session.get("calc_correct_count", 0)

    if value == expected:
        correct_count += 1
        request.session["calc_correct_count"] = correct_count

    operation = generate_operation(level)
    request.session["calc_answer"] = operation["answer"]

    return {"correct": value == expected, "correct_count": correct_count, "next_operation": operation}


@router.post("/games/calculation/finish")
def calculation_finish(request: Request, current_user=Depends(get_current_user_or_redirect), db: Session = Depends(get_db)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    correct_count = request.session.get("calc_correct_count", 0)
    level = request.session.get("calc_level", 1)

    score, xp = calculate_score(correct_count, level)

    result = GameResult(user_id=current_user.id, game_type="calculation", score=score, xp_earned=xp, duration=CALCULATION_DURATION)
    db.add(result)
    current_user.xp += xp
    current_user.total_score += score
    current_user.games_played += 1
    db.commit()

    request.session.pop("calc_answer", None)
    request.session.pop("calc_level", None)
    request.session.pop("calc_correct_count", None)

    return {"correct_count": correct_count, "score": score, "xp_earned": xp}


@router.get("/leaderboard", response_class=HTMLResponse)
def leaderboard(request: Request, page: int = 1, current_user=Depends(get_current_user_or_redirect), db: Session = Depends(get_db)):
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
        context={"users": users, "page": page, "your_rank": your_rank, "start_rank": offset + 1},
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={})


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html", context={})