from src.common.rounding import to_cents


def invoice_total(amounts):
    return sum(to_cents(a) for a in amounts)
