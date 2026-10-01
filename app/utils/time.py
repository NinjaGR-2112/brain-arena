"""Horloge UTC du projet.

Les colonnes ``DateTime`` des modèles sont déclarées *sans* fuseau horaire
(pas ``timezone=True``), et SQLite comme PostgreSQL renvoient donc des
``datetime`` **naifs** à la lecture. Stocker des datetimes conscients dans ces
colonnes produit des valeurs qui se comparent mal en Python
(``TypeError: can't compare offset-naive and offset-aware datetimes``).

Tout le projet passe par :func:`utcnow`, qui renvoie systématiquement une
heure UTC **naive**, cohérente en écriture comme en lecture.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Heure UTC actuelle, naive — directement stockable dans une colonne ``DateTime``."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
