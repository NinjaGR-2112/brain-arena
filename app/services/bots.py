"""Le bot : difficulte dosee, puis passage dans le moteur de score existant.

Principe : **aucune formule de score n'est invente ici**. Le bot tire son coup
au hasard dans une bande adaptee a sa difficulte, puis on le fait passer par
les memes fonctions que le joueur —
:func:`app.services.scoring.calculate_memory_score`,
:func:`app.games.calculation.calculate_score` et
:func:`app.games.reaction.score_reaction_round`. Un changement de bareme
profite donc aux deux cotes du duel, et un bot ne peut pas marquer un score
qu'un joueur ne pourrait pas marquer.

Le niveau de jeu est **interne** : il dose la force de l'adversaire et
s'applique aux deux joueurs, ce qui garde le duel equitable. Le joueur ne le
voit a aucun moment.
"""
import random

from app.games.calculation import calculate_score as calculate_calculation_score
from app.games.reaction import score_reaction_round
from app.services.scoring import calculate_memory_score

# Difficulte, du plus faible au plus fort. L'ordre fait reference : les tests
# et le dosage par XP s'appuient dessus.
DIFFICULTIES = ("rookie", "regular", "veteran", "elite")

# Niveau interne par difficulte et par jeu. Memory en compte 4, Calculation 3,
# Reaction 0 (ses rounds sont identiques) — d'ou le niveau 1 de repli.
DUEL_LEVELS = {
    "memory": {"rookie": 1, "regular": 2, "veteran": 3, "elite": 4},
    "calculation": {"rookie": 1, "regular": 1, "veteran": 2, "elite": 3},
    "reaction": {difficulty: 1 for difficulty in DIFFICULTIES},
}

# Memory : (probabilite de reussite, duree de reponse minimale, maximale).
# La borne haute reste sous les 10 s du bonus de vitesse, sinon le bot
# n'aurait jamais de bonus et paraitrait lent.
MEMORY_BANDS = {
    "rookie": (0.50, 2.0, 9.5),
    "regular": (0.65, 2.0, 8.5),
    "veteran": (0.80, 1.8, 7.5),
    "elite": (0.92, 1.5, 6.5),
}

# Calculation : bornes du nombre de bonnes reponses sur 30 secondes.
CALCULATION_BANDS = {
    "rookie": (2, 5),
    "regular": (4, 9),
    "veteran": (7, 14),
    "elite": (11, 20),
}

# Reaction : bornes du temps de reponse, en millisecondes. Toutes restent
# au-dessus du seuil humain de 120 ms : un bot ne triche pas sur le temps,
# il est simplement plus ou moins rapide.
REACTION_BANDS = {
    "rookie": (400, 900),
    "regular": (300, 600),
    "veteran": (220, 420),
    "elite": (160, 260),
}

# Seuils d'XP decrivant la difficulté de base. Au-dela du dernier seuil, le
# joueur tombe dans la categorie la plus forte.
XP_TIERS = (200, 800, 2000)

# Amplitude du tirage autour de la categorie de base. Un joueur peut donc
# tomber sur un bot d'une difficulte voisine, jamais de deux crans.
JITTER_CHOICES = (-1, 0, 0, 1)


def duel_level(game_type: str, difficulty: str) -> int:
    """Niveau interne d'une partie, partage par le joueur et le bot."""
    return DUEL_LEVELS[game_type][difficulty]


def bot_score(game_type: str, difficulty: str, rng: random.Random | None = None) -> int:
    """Score du bot, calcule par le moteur de score des joueurs.

    Le tirage est fait une seule fois, au lancement du duel : le bot ne
    rejoue jamais en fonction de ce que fait le joueur.
    """
    rng = rng or random.Random()

    if game_type == "memory":
        level = duel_level("memory", difficulty)
        hit_rate, fastest, slowest = MEMORY_BANDS[difficulty]
        correct = rng.random() < hit_rate
        time_taken = rng.uniform(fastest, slowest)
        score, _ = calculate_memory_score(level, correct, time_taken)
        return score

    if game_type == "calculation":
        level = duel_level("calculation", difficulty)
        fewest, most = CALCULATION_BANDS[difficulty]
        correct_count = rng.randint(fewest, most)
        score, _ = calculate_calculation_score(correct_count, level)
        return score

    if game_type == "reaction":
        fastest, slowest = REACTION_BANDS[difficulty]
        scores = [
            score_reaction_round(rng.uniform(fastest, slowest))[0] for _ in range(5)
        ]
        return sum(scores) // len(scores)

    raise ValueError(f"Unknown game type: {game_type}")


def base_difficulty(xp: int) -> str:
    """Categorie de difficulte correspondant a l'XP du joueur."""
    for index, threshold in enumerate(XP_TIERS):
        if xp < threshold:
            return DIFFICULTIES[index]
    return DIFFICULTIES[-1]


def pick_difficulty(xp: int, rng: random.Random | None = None) -> str:
    """Difficulte du bot, dosee sur l'XP du joueur.

    Le tirage est borne a un cran de part et d'autre de la categorie de base :
    un debutant ne tombe jamais sur un bot d'elite, et un expert ne redescend
    jamais au niveau debutant.
    """
    rng = rng or random.Random()
    index = DIFFICULTIES.index(base_difficulty(xp))
    index = max(0, min(len(DIFFICULTIES) - 1, index + rng.choice(JITTER_CHOICES)))
    return DIFFICULTIES[index]
