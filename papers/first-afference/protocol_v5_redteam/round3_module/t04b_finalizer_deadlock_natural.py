# Default GC thresholds, no gc tuning: a per-item battery whose items leave cyclic garbage with a
# finalizer that calls a declared target (a resource's close()/flush()). The GC eventually fires
# while section()'s bookkeeping holds the tracer's non-reentrant _lock -> self-deadlock.
import gc, sys, faulthandler, time
faulthandler.dump_traceback_later(int(sys.argv[2]) if len(sys.argv) > 2 else 60, exit=True)
from rtlib import *
import fx_simple
class Res:
    def __init__(self): self.me = self; self.buf = [{} for _ in range(3)]
    def __del__(self): fx_simple.f()
e = exp(spec(G={"exercises": ["fx_simple:f"]}))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
t0 = time.time()
with coverage_trace(e) as cov:
    for i in range(N):
        with cov.section("G"):
            Res(); fx_simple.f()
print("ok", N, "sections in %.1fs" % (time.time() - t0))
