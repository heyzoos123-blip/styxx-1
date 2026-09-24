from rtlib import *
import fx_simple as fx, sys, traceback
e = exp(spec(G={"exercises": ["fx_simple:f"]}))
print("profiler before:", sys.getprofile())
try:
    with coverage_trace(e) as cov:
        with cov.section("G"):
            fx.f()
    print("scored:", score(e, cov.record()))
except BaseException as ex:
    print("ESCAPED:", type(ex).__name__, ex)
print("profiler after:", sys.getprofile())
