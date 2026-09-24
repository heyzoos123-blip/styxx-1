from rtlib import *
import fx3_factory as m
def a():
    e = exp(spec(G={"exercises": ["fx3_factory:double"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            triple_result = m.make_mul(3)(5)        # the harness only ever uses a *triple*
    r = cov.record(); print("   impostors:", r["impostors"], "close_refusals:", r["close_refusals"])
    return score(e, r)
attempt("P1 defaults-only factory product (triple) credited as declared 'double'", a)
def b():
    e = exp(spec(G={"exercises": ["fx3_factory:score_lenient"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            m.make_scorer(abs, True)(3)              # the strict scorer only
    r = cov.record(); print("   impostors:", r["impostors"], "close_refusals:", r["close_refusals"])
    return score(e, r)
attempt("P2 same closure objects, different default -> credited as declared lenient scorer", b)
def c():
    e = exp(spec(G={"exercises": ["fx3_factory:score_lenient"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            m.make_scorer(len, False)("ab")          # different closure object: must be impostor
    r = cov.record(); print("   impostors:", r["impostors"])
    return score(e, r)
attempt("P3 control: different closure object", c)
