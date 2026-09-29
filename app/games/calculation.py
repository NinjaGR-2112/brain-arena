import random


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


def calculate_score(correct_count: int, level: int) -> tuple[int, int]:
    score = correct_count * 20 * level
    xp = score // 10
    return score, xp