from app.services.scoring import calculate_memory_score


def test_memory_score_correct_answer():
    score, xp = calculate_memory_score(level=1, correct=True, time_taken=3.0)
    assert score > 0
    assert xp > 0


def test_memory_score_wrong_answer():
    score, xp = calculate_memory_score(level=1, correct=False, time_taken=3.0)
    assert score == 0


def test_memory_score_faster_gives_more_points():
    slow_score, _ = calculate_memory_score(level=1, correct=True, time_taken=8.0)
    fast_score, _ = calculate_memory_score(level=1, correct=True, time_taken=1.0)
    assert fast_score > slow_score


def test_memory_score_higher_level_gives_more_points():
    level1_score, _ = calculate_memory_score(level=1, correct=True, time_taken=3.0)
    level4_score, _ = calculate_memory_score(level=4, correct=True, time_taken=3.0)
    assert level4_score > level1_score