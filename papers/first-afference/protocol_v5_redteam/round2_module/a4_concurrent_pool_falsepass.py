# Gates A and B run concurrently in two runner threads (started outside any section) and share
# one ThreadPoolExecutor. A's own work never calls f. B calls f through the pool. The pool's
# single worker was spawned by A's first submit, so it is mapped to section A forever, and B's
# call to f is credited to A while A is still open.
from rtlib import *
import fx_simple as fs, threading
from concurrent.futures import ThreadPoolExecutor
def run():
    e = exp(spec(A={"exercises": ["fx_simple:f"]}, B={"exercises": ["fx_simple:g"]}))
    errs = []
    with coverage_trace(e) as cov:
        pool = ThreadPoolExecutor(1)
        a_submitted = threading.Event(); pool_down = threading.Event()
        def gate_a():
            try:
                with cov.section("A"):
                    pool.submit(fs.g).result()   # A's work: g only -- f is never called by A
                    a_submitted.set()
                    pool_down.wait()             # A waits for the shared pool to drain
            except Exception as ex: errs.append(repr(ex)[:150])
        def gate_b():
            try:
                a_submitted.wait()
                with cov.section("B"):
                    fs.g()                       # B's direct work
                    pool.submit(fs.f).result()   # B's pooled work
            except Exception as ex: errs.append(repr(ex)[:150])
        ta, tb = threading.Thread(target=gate_a), threading.Thread(target=gate_b)
        ta.start(); tb.start(); tb.join()
        pool.shutdown(wait=True); pool_down.set(); ta.join()
    r = cov.record()
    return f"errs={errs} sections={r['sections']}\n   " + score(e, r)
attempt("A4 concurrent sections + shared pool: A never calls f", run)
