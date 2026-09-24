from rtlib import *
import fx_simple as fs, threading
def run():
    e = exp(spec(A={"exercises": ["fx_simple:f"]}, B={"exercises": ["fx_simple:g"]}))
    with coverage_trace(e) as cov:
        go = threading.Event(); done = threading.Event()
        def child():
            go.wait(); t2 = threading.Thread(target=fs.g); t2.start(); t2.join(); done.set()
        try:
            with cov.section("A"):
                fs.f(); t1 = threading.Thread(target=child); t1.start()
                raise ValueError("expected")      # exception exit skips THREAD_OUTLIVES
        except ValueError: pass
        with cov.section("B"):
            go.set(); done.wait()                 # grandchild calls g while B is open
        t1.join()
    r = cov.record(); return score(e, r) + f" after_close={r['after_close']}"
attempt("A11 grandchild thread started after A closed, while B open", run)
