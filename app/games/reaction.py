import random
import time


def generate_delay() -> float:
    """Délai aléatoire avant le signal, entre 1.5 et 4 secondes."""
    return random.uniform(1.5, 4.0)


def calculate_round_score(reaction_time_ms: float) -> int:
    """Score d'un round : plus c'est rapide, plus c'est élevé."""
    if reaction_time_ms < 0:
        return 0  # clic avant le signal, traité côté route
    score = max(0, 1000 - int(reaction_time_ms))
    return score