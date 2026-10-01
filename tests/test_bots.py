"""Le bot joue côté serveur, avec le moteur de score existant.

Aucune formule inventée ici : le bot tire son coup au hasard dans une bande
adaptée à sa difficulté, puis on le fait passer par
:func:`app.services.scoring.calculate_memory_score`,
:func:`app.games.calculation.calculate_score` et
:func:`app.games.reaction.score_reaction_round` — exactement comme un joueur.
Un changement de barème profite donc aux deux côtés du duel.
"""
import random

import pytest

from app.games.calculation import LEVELS as CALCULATION_LEVELS
from app.games.calculation import MAX_CORRECT_ANSWERS
from app.games.memory import LEVELS as MEMORY_LEVELS
from app.games.reaction import TOTAL_ROUNDS
from app.services.bots import (
    DIFFICULTIES,
    REACTION_BANDS,
    bot_score,
    duel_level,
    pick_difficulty,
)


# ---------------------------------------------------------------------------
# Difficulté dosée
# ---------------------------------------------------------------------------


def test_difficulty_is_dosed_by_xp():
    """Un débutant ne tombe pas sur un bot d'élite, et inversement."""
    assert pick_difficulty(0, random.Random(1)) in ("rookie", "regular")
    assert pick_difficulty(10_000, random.Random(1)) in ("veteran", "elite")


def test_difficulty_never_leaves_the_ladder():
    rng = random.Random(7)
    for xp in range(0, 6_000, 37):
        assert pick_difficulty(xp, rng) in DIFFICULTIES


def test_difficulty_jitter_never_exceeds_one_tier():
    rng = random.Random(3)
    beginners = {pick_difficulty(0, rng) for _ in range(200)}
    veterans = {pick_difficulty(10_000, rng) for _ in range(200)}

    assert beginners <= {"rookie", "regular"}
    assert veterans <= {"veteran", "elite"}


def test_difficulty_rises_with_xp_on_average():
    """Le dosage doit être monotone en moyenne, pas à chaque tirage."""
    rng = random.Random(11)
    average_of = lambda xp: sum(
        DIFFICULTIES.index(pick_difficulty(xp, rng)) for _ in range(200)
    ) / 200

    assert average_of(10_000) > average_of(1_000) > average_of(0)


# ---------------------------------------------------------------------------
# Niveau interne : partagé par le joueur et le bot
# ---------------------------------------------------------------------------


def test_duel_levels_stay_inside_each_games_ladder():
    for difficulty in DIFFICULTIES:
        assert duel_level("memory", difficulty) in MEMORY_LEVELS
        assert duel_level("calculation", difficulty) in CALCULATION_LEVELS


def test_duel_level_rises_with_difficulty():
    for game_type in ("memory", "calculation"):
        levels = [duel_level(game_type, difficulty) for difficulty in DIFFICULTIES]
        assert levels == sorted(levels), game_type


def test_reaction_has_no_level_to_choose():
    """Reaction se joue en rounds identiques : le niveau n'y dose rien."""
    assert {duel_level("reaction", difficulty) for difficulty in DIFFICULTIES} == {1}


# ---------------------------------------------------------------------------
# Les scores du bot restent dans les bornes du moteur
# ---------------------------------------------------------------------------


def test_bot_memory_score_stays_inside_engine_bounds():
    for difficulty in DIFFICULTIES:
        level = duel_level("memory", difficulty)
        ceiling = level * 100 + 100  # base + bonus de vitesse maximal

        for seed in range(50):
            score = bot_score("memory", difficulty, random.Random(seed))
            assert 0 <= score <= ceiling


def test_bot_calculation_score_is_a_multiple_of_the_formula():
    """score = bonnes réponses × 20 × niveau : rien d'autre ne peut sortir."""
    for difficulty in DIFFICULTIES:
        level = duel_level("calculation", difficulty)

        for seed in range(50):
            score = bot_score("calculation", difficulty, random.Random(seed))
            assert score % (20 * level) == 0
            assert 0 < score <= MAX_CORRECT_ANSWERS * 20 * level


def test_bot_reaction_score_is_a_plausible_human_average():
    """Un bot ne peut pas marcher sur le garde-fou des 120 ms : ses temps
    restent humains, donc son score reste sous le plafond du jeu."""
    for difficulty in DIFFICULTIES:
        low_ms, high_ms = REACTION_BANDS[difficulty]
        floor, ceiling = 1_000 - high_ms, 1_000 - low_ms

        for seed in range(50):
            score = bot_score("reaction", difficulty, random.Random(seed))
            assert floor <= score <= ceiling
            assert 0 < score < 1_000


def test_bot_reaction_score_averages_exactly_five_rounds():
    assert TOTAL_ROUNDS == 5  # la moyenne du bot suit la règle du jeu


def test_unknown_game_is_refused():
    with pytest.raises(ValueError):
        bot_score("chess", "rookie")


# ---------------------------------------------------------------------------
# Une difficulté plus forte doit réellement marquer plus
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("game_type", ["memory", "calculation", "reaction"])
def test_a_stronger_bot_scores_more_on_average(game_type):
    draws = 300

    rookie = sum(bot_score(game_type, "rookie", random.Random(s)) for s in range(draws))
    elite = sum(bot_score(game_type, "elite", random.Random(s)) for s in range(draws))

    assert elite > rookie, game_type
