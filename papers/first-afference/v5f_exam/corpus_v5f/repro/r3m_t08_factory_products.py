"""round3_module/t08_factory_products.py, rewritten: P1 a defaults-only factory product (triple) where 'double'
is declared; P2 the same closure objects with a different default (strict scorer) where the lenient scorer is
declared; P3 control, a different closure object."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r3m_fx import FACTORY


def main(api):
    m = api.fixture("rp_fx3_factory", FACTORY)
    T = lambda t, fn: api.trace(api.exp({"G": [f"rp_fx3_factory:{t}"]}), lambda c: c.run("G", fn))
    return {"P1": T("double", lambda: m.make_mul(3)(5)), "P2": T("score_lenient", lambda: m.make_scorer(abs, True)(3)),
            "P3": T("score_lenient", lambda: m.make_scorer(len, False)("ab"))}
