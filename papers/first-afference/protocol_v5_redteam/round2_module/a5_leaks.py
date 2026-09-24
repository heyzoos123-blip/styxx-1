from rtlib import *
import fx_simple as fs, threading, time, sys, queue
from concurrent.futures import ThreadPoolExecutor
def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)

def worker_keeps_hook():
    # a long-lived worker pool (e.g. a server's executor) that happens to spawn a thread while tracing
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    pool = ThreadPoolExecutor(1)
    with coverage_trace(e) as cov:
        with cov.section("G"): fs.f()
        pool.submit(lambda: None).result()        # worker spawned during trace, outside sections
    t0 = time.perf_counter(); fib(22); main_t = time.perf_counter() - t0
    def timed():
        t0 = time.perf_counter(); fib(22); return time.perf_counter() - t0, sys.getprofile()
    wt, prof = pool.submit(timed).result()
    pool.shutdown()
    return f"after trace exit: worker profile={type(prof).__name__} tracer active={prof.tracer._active if prof else None}; fib(22) main={main_t:.3f}s worker={wt:.3f}s ({wt/main_t:.1f}x)"
attempt("A5a thread spawned during trace keeps hook after exit", worker_keeps_hook)

def exit_order_leaves_threading_hook():
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    try:
        with coverage_trace(e) as cov:
            with cov.section("G"): fs.f()
            sys.setprofile(None)      # e.g. a library/debugger clears the profiler after the section
    except GateSpecError as ex: print("   exit:", str(ex)[:50])
    return f"sys={sys.getprofile()} threading={threading.getprofile()}"
attempt("A5b EXIT_ORDER path leaves threading profile installed", exit_order_leaves_threading_hook)

def exc_exit_with_replaced():
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    def myprof(*a): pass
    try:
        with coverage_trace(e) as cov:
            with cov.section("G"):
                fs.f(); sys.setprofile(myprof); raise KeyError("x")
    except KeyError: pass
    return f"sys={sys.getprofile()} threading={threading.getprofile()}"
attempt("A5c exception exit after profiler replaced", exc_exit_with_replaced)

def blind_window():
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            old = sys.getprofile(); sys.setprofile(None); fs.f(); sys.setprofile(old)
    return score(e, cov.record())
attempt("A5d blind window then restore (f only called in window)", blind_window)

def cross_thread_tracers():
    e = exp(spec(G={"exercises": ["fx_simple:f"]})); e2 = exp(spec(H={"exercises": ["fx_simple:g"]}))
    t1 = coverage_trace(e); t1.__enter__()
    ready = threading.Event(); go = threading.Event(); out = {}
    def other():
        t2 = coverage_trace(e2); t2.__enter__(); ready.set(); go.wait()
        try: t2.__exit__(None, None, None)
        except GateSpecError as ex: out['t2'] = str(ex)[:40]
    th = threading.Thread(target=other); th.start(); ready.wait()
    try: t1.__exit__(None, None, None)
    except GateSpecError as ex: out['t1'] = str(ex)[:40]
    go.set(); th.join()
    return f"{out} main sys={sys.getprofile()} threading={threading.getprofile()}"
attempt("A5e two tracers in two threads", cross_thread_tracers)
