from rtlib import *
import fx_factory as fx
# 1) factory-made functions: declared check_high, harness only calls check_low
e = exp(spec(G={"exercises": ["fx_factory:check_high"]}))
with coverage_trace(e) as cov:
    with cov.section("G"):
        fx.check_low(0.5)
print("factory closure:", score(e, cov.record()))
# 2) decorator without wraps: declared entry_b, harness only calls entry_a
e = exp(spec(G={"exercises": ["fx_factory:entry_b"]}))
with coverage_trace(e) as cov:
    with cov.section("G"):
        fx.entry_a()
print("no-wraps decorator:", score(e, cov.record()))
# 3) decorator without wraps: declared entry_b, called nothing but the undecorated... wrapper of entry_a even if inner is not reached
