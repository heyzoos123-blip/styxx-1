from rtlib import *
import fx_simple as fx, threading, sys
from concurrent.futures import ThreadPoolExecutor
e = exp(spec(G={"exercises": ["fx_simple:f"]}))

# (a) an executor whose worker already exists before the trace (warm pool)
pool = ThreadPoolExecutor(1); pool.submit(lambda: None).result()
with coverage_trace(e) as cov:
    with cov.section("G"):
        assert pool.submit(fx.f).result() == 1      # f really runs, in the section
print("(a) warm thread pool:", score(e, cov.record()))

# (b) two gates' sections run in parallel threads
e2 = exp(spec(A={"exercises": ["fx_simple:f"]}, B={"exercises": ["fx_simple:g"]}))
errs = []
with coverage_trace(e2) as cov:
    bar = threading.Barrier(2)
    def run(name, fn):
        try:
            bar.wait()
            with cov.section(name):
                import time; time.sleep(0.05); fn()
        except Exception as ex: errs.append(f"{type(ex).__name__}: {str(ex)[:90]}")
    ts = [threading.Thread(target=run, args=a) for a in (("A", fx.f), ("B", fx.g))]
    [t.start() for t in ts]; [t.join() for t in ts]
print("(b) parallel sections:", errs, "|", score(e2, cov.record()))

# (c) harness profiles its own section with cProfile
import cProfile
with coverage_trace(e) as cov:
    with cov.section("G"):
        pr = cProfile.Profile(); pr.enable(); fx.f(); pr.disable()
print("(c) cProfile inside section:", score(e, cov.record()))
print("    profiler after exit:", sys.getprofile())
