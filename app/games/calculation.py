import random

LEVELS: tuple[int, ...] = (1, 2, 3)

# Durée de la partie. Le minuteur affiché au client n'est qu'indicatif :
# c'est l'expiration de la GameSession côté serveur qui fait foi.
CALCULATION_DURATION = 30

# Marge réseau ajoutée à la durée pour que le ``/finish`` déclenché par le
# minuteur du navigateur ne soit pas rejeté à cause de la latence.
FINISH_GRACE_SECONDS = 5

# Intervalle minimal entre deux réponses acceptées. Un humain ne descend pas
# sous ~0,3 s ; cela borne le débit d'un script.
MIN_ANSWER_INTERVAL_SECONDS = 0.25

# Plafond de bonnes réponses sur une partie de 30 s.
MAX_CORRECT_ANSWERS = 40


def generate_operation(level: int) -> dict:
    if level == 1:
        a, b = random.randint(1, 50), random.randint(1, 50)
        op = random.choice(["+", "-"])
    elif level == 2:
        a, b = random.randint(2, 12), random.randint(2, 12)
        op = "×"
    else:
        a, b = random.randint(10, 99), random.randint(2, 12)
        op = random.choice(["+", "-", "×"])

    if op == "+":
        answer = a + b
    elif op == "-":
        answer = a - b
    else:
        answer = a * b

    return {"a": a, "b": b, "op": op, "answer": answer}


def public_operation(operation: dict) -> dict:
    """Opération privée de sa réponse.

    C'est la seule forme transmise au client. La bonne réponse restait
    auparavant dans le JSON renvoyé par ``/games/calculation/answer``.
    """
    return {"a": operation["a"], "b": operation["b"], "op": operation["op"]}


def calculate_score(correct_count: int, level: int) -> tuple[int, int]:
    score = correct_count * 20 * level
    xp = score // 10
    return score, xp
