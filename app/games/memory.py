import random

# Longueur de la séquence par niveau. C'est aussi la liste des niveaux valides.
LEVEL_LENGTHS: dict[int, int] = {1: 4, 2: 5, 3: 6, 4: 7}
LEVELS: tuple[int, ...] = tuple(LEVEL_LENGTHS)

# Le client voit la séquence 3 s (cf. memory.html), puis la saisit. La fenêtre
# serveur est volontairement large : la lenteur ne rapporte rien au joueur
# (le bonus de vitesse décroît), l'anti-triche repose sur le jeton à usage
# unique et non sur ce délai.
ANSWER_WINDOW_SECONDS = 60


def generate_sequence(level: int) -> list[int]:
    """Génère une séquence de chiffres aléatoires selon le niveau."""
    length = LEVEL_LENGTHS.get(level, LEVEL_LENGTHS[1])
    return [random.randint(0, 9) for _ in range(length)]
