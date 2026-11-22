from src.total import total


def test_total_small():
    r = total([1, 2, 3])
    assert type(r) is int
    assert r == 6


def test_total_same_call_two_answers():
    r = total([1, 2, 3])
    assert type(r) is int
    assert r == 6
    assert r == 7
