# Cost of a section close: gc.collect() + gc.get_referrers() (a full-heap scan) for every declared
# target, on every close. A per-item battery on a realistic heap.
import sys, time, gc
from rtlib import *
import fx_simple
heap_objs = int(sys.argv[1])
keep = [[i] for i in range(heap_objs)]          # stands in for a loaded dataset/model
e = exp(spec(G={"exercises": ["fx_simple:f", "fx_simple:g"]}))
with coverage_trace(e) as cov:
    t0 = time.time()
    for i in range(20):
        with cov.section("G"):
            fx_simple.f(); fx_simple.g()
    per = (time.time() - t0) / 20
print(f"heap ~{len(gc.get_objects())/1e6:.1f}M tracked objects: {per*1000:.0f} ms per section close"
      f" -> a 1000-item per-item battery spends {per*1000/60:.1f} min in close bookkeeping")
