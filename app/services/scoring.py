def calculate_memory_score(level: int, correct: bool, time_taken: float) -> tuple[int, int]:
    """Retourne (score, xp_earned) pour une partie de Memory."""
    if not correct:
        return 0, 5  # petit XP de consolation même en cas d'échec

    base_score = level * 100
    speed_bonus = max(0, int((10 - time_taken) * 10))
    score = base_score + speed_bonus
    xp = score // 10

    return score, xp