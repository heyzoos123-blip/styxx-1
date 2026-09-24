# A finalizer (cyclic garbage's __del__) that calls a declared target runs whenever the GC fires.
# If the GC fires while this thread holds the tracer's non-reentrant _lock OUTSIDE the hook
# (section() open bookkeeping, close(), record()), the finalizer's call enters the hook, which
# takes _lock again -> self-deadlock. We sweep the gen-0 threshold so the collection lands at
# each allocation in turn; argv[1] = where, argv[2] = k.
import gc, sys, faulthandler
faulthandler.dump_traceback_later(5, exit=True)
from rtlib import *
import fx_simple
class Res:
    def __init__(self): self.me = self
    def __del__(self): fx_simple.f()            # e.g. close()/flush() calling a declared function
e = exp(spec(G={"exercises": ["fx_simple:f"]}))
where, k = sys.argv[1], int(sys.argv[2])
with coverage_trace(e) as cov:
    if where == "record":
        with cov.section("G"): fx_simple.f()
        gc.collect(); gc.disable()
        for _ in range(5): Res()
        gc.set_threshold(k); gc.enable()
        r = cov.record()
    else:
        gc.collect(); gc.disable()
        for _ in range(5): Res()
        gc.set_threshold(k); gc.enable()
        with cov.section("G"):
            fx_simple.f()
    gc.set_threshold(700)
print("ok")
