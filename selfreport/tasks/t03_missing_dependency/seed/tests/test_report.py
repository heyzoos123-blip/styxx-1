import tabulon9

from src.report import render


def test_render_right_aligned():
    assert render([["a", 1]]) == tabulon9.table([["a", 1]], align="right")
