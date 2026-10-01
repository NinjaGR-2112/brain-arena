"""Bornage des niveaux de jeu.

``level`` arrive de l'URL, donc du client. Sans contrôle, ``?level=1000000``
donnait un score de 100 000 099 points en une seule partie de Memory. Le
niveau est désormais ramené à la liste autorisée par chaque jeu.
"""


def clamp_level(requested: int, allowed: tuple[int, ...]) -> int:
    """Ramène un niveau demandé à la valeur autorisée la plus proche.

    Le niveau le plus proche est préféré au niveau minimal : un joueur qui
    demande le niveau 4 d'un jeu qui en compte 4 obtient bien le niveau 4,
    et non un niveau rétrogradé qui fausserait son score.
    """
    if requested in allowed:
        return requested
    return min(allowed, key=lambda level: (abs(level - requested), level))
