from rtlib import *
import fx2_inst, fx2_wraps, fx2_sd
def inst():
    # declares the method as reached through a module-level Sub instance; Sub is never used
    e = exp(spec(G={"exercises": ["fx2_inst:default_model.fit"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"): fx2_inst.Other().fit()
    return score(e, cov.record())
attempt("A2a INHERITED bypass via instance path", inst)
def wr():
    e = exp(spec(G={"exercises": ["fx2_wraps:run_fast"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"): fx2_wraps.run_safe(1)     # run_fast never called
    return score(e, cov.record())
attempt("A2b wraps-variant aliasing via inspect.unwrap", wr)
def sd():
    e = exp(spec(G={"exercises": ["fx2_sd:process"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"): fx2_sd.process(5)          # process() really called (int impl)
    return score(e, cov.record())
attempt("A2c singledispatch: public entry really called", sd)
