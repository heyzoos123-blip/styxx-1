from rtlib import *
import fx_simple as fx, threading, time
from concurrent.futures import ThreadPoolExecutor
# Gate A (section A) exercises f; gate B (section B) exercises g.
e = exp(spec(A={"exercises": ["fx_simple:f"]}, B={"exercises": ["fx_simple:g"]}))
with coverage_trace(e) as cov:
    with cov.section("A"):
        fx.f()
        # A's work also kicks off a background job that calls g later (not joined here)
        ex = ThreadPoolExecutor(1); ex.submit(fx.slow_then_g, 0.2); ex.shutdown(wait=False)
    with cov.section("B"):
        time.sleep(0.5)            # B's own work never calls g
    ex.shutdown(wait=True)
print("thread outlives section A, g lands in B:", score(e, cov.record()))
print(cov.record()["sections"])

# a thread started BEFORE any section, doing unrelated work that happens to overlap B
e = exp(spec(B={"exercises": ["fx_simple:g"]}))
with coverage_trace(e) as cov:
    t = threading.Thread(target=fx.slow_then_g, args=(0.1,)); t.start()
    with cov.section("B"):
        time.sleep(0.3)
    t.join()
print("background thread started outside any section:", score(e, cov.record()))
