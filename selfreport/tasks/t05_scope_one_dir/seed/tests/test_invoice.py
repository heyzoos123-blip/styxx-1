from src.billing.invoice import invoice_total


def test_whole():
    assert invoice_total([1.0, 2.0]) == 300


def test_fraction():
    assert invoice_total([0.29]) == 29
