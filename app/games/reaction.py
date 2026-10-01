import random

TOTAL_ROUNDS = 5

# Temps de réaction visuel humain plancher : ~150-200 ms. En dessous de
# 120 ms, la valeur ne peut pas provenir d'un humain mais d'un script qui
# répond dès la réception du signal (5 à 8 ms mesurées en pratique).
MIN_HUMAN_REACTION_MS = 120

# Au-delà, le joueur a abandonné : le round est nul, mais la partie continue.
MAX_VALID_REACTION_MS = 10_000

# Durée de vie d'une partie complète de Reaction.
GAME_TTL_SECONDS = 600

# Fenêtre accordée entre le signal et le clic d'un round.
ROUND_WINDOW_SECONDS = 30


def generate_delay() -> float:
    """Délai aléatoire avant le signal, entre 1.5 et 4 secondes."""
    return random.uniform(1.5, 4.0)


def calculate_round_score(reaction_time_ms: float) -> int:
    """Score d'un round : plus c'est rapide, plus c'est élevé."""
    if reaction_time_ms < 0:
        return 0  # clic avant le signal, traité côté route
    score = max(0, 1000 - int(reaction_time_ms))
    return score


def score_reaction_round(reaction_time_ms: float) -> tuple[int, bool]:
    """Score un round en écartant les temps physiquement impossibles.

    Renvoie ``(score, too_fast)``. Un temps sous :data:`MIN_HUMAN_REACTION_MS`
    rapporte 0 : c'est ce garde-fou qui empêche un client automatisé de
    récolter un score quasi parfait à chaque partie.
    """
    if reaction_time_ms < MIN_HUMAN_REACTION_MS:
        return 0, True
    if reaction_time_ms > MAX_VALID_REACTION_MS:
        return 0, False
    return calculate_round_score(reaction_time_ms), False
