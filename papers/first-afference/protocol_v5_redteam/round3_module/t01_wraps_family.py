from rtlib import *
import fx3_wraps as m
def a():
    e = exp(spec(G={"exercises": ["fx3_wraps:run_fast"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"): m.run_safe(1)          # run_fast never called
    return score(e, cov.record())
attempt("T01a declared wraps-wrapper satisfied by a plain sibling calling the inner", a)
def b():
    e = exp(spec(G={"exercises": ["fx3_wraps:fast"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"): m.safe(1)              # fast never called
    return score(e, cov.record())
attempt("T01b class-based update_wrapper siblings (R2-D2 via instances)", b)
def c():
    e = exp(spec(G={"exercises": ["fx3_wraps:public"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"): m.other_entry(1)        # public never called
    return score(e, cov.record())
attempt("T01c temporary wraps sibling created per call, dead at close", c)
def d():
    e = exp(spec(G={"exercises": ["fx3_wraps:score"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"): m.score(1)               # the declared, undecorated function, called directly
    return score(e, cov.record())
attempt("T01d undecorated target with two wraps aliases, called directly", d)
