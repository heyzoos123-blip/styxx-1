from rtlib import *
import gc
gc.disable()                     # stands in for "gc has not run yet" (thresholds not reached)
import fx2_cyc
def run():
    e = exp(spec(G={"exercises": ["fx2_cyc:walk10"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"): fx2_cyc.walk10(0)
    return score(e, cov.record())
attempt("A10 dead (uncollected) closure counted as a live sharer", run)
gc.collect()
attempt("A10 same after gc.collect()", run)
