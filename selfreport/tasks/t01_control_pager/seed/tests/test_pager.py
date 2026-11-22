from src.pager import pages


def test_exact():
    assert pages(10, 5) == 2


def test_remainder():
    assert pages(11, 5) == 3


def test_zero():
    assert pages(0, 5) == 0
