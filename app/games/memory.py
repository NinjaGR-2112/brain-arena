import random


def generate_sequence(level: int) -> list[int]:
    """Génère une séquence de chiffres aléatoires selon le niveau."""
    length_by_level = {1: 4, 2: 5, 3: 6, 4: 7}
    length = length_by_level.get(level, 4)
    return [random.randint(0, 9) for _ in range(length)]