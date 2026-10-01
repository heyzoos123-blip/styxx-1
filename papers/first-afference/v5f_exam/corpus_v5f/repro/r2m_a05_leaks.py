"""round2_module/a5_leaks.py, rewritten: a a pool worker spawned during the trace, outside sections: what it sees
after the exit (the profiler, styxx's tool, the fixture's local events; the repro's timing ratio is not an
observable); b the profiler cleared inside the trace after the section; c an exception exit after the profiler was
replaced in the section; d a blind window (profiler cleared, f called, restored) inside the section; e two
tracers entered in two threads, the main thread's exited first."""
import os, sys, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
from r2m_fx import SIMPLE


def main(api):
    fs = api.fixture("rp_fx_simple", SIMPLE)
    mon = getattr(sys, "monitoring", None)
    hooks = lambda: {"getprofile_none": sys.getprofile() is None, "threading_getprofile_none": threading.getprofile() is None,
                     "f_local_events": mon.get_local_events(api.P._v5_state().get("tool") or 0, fs.f.__code__) if mon else None}
    E = lambda: api.exp({"G": ["rp_fx_simple:f"]})
    out = {}
    pool = ThreadPoolExecutor(1)
    out["a"] = api.trace(E(), lambda c: c.run("G", fs.f), lambda c: pool.submit(lambda: None).result())
    out["a_worker_after_exit"] = pool.submit(lambda: (sys.getprofile() is None, fs.f())).result()
    out["a_hooks"] = hooks()
    pool.shutdown()

    def clear(c):
        sys.setprofile(None)
    out["b"] = api.trace(E(), lambda c: c.run("G", fs.f), clear)
    out["b_hooks"] = hooks()

    def myprof(*a):
        pass

    def body():
        fs.f()
        sys.setprofile(myprof)
        raise KeyError("x")
    out["c"] = api.trace(E(), lambda c: c.run("G", body))
    out["c_profile_is_myprof"] = sys.getprofile() is myprof
    sys.setprofile(None)
    out["c_hooks"] = hooks()

    def blind():
        old = sys.getprofile()
        sys.setprofile(None)
        fs.f()
        sys.setprofile(old)
    out["d"] = api.trace(E(), lambda c: c.run("G", blind))
    e, e2 = E(), api.exp({"H": ["rp_fx_simple:g"]})
    t1 = api.coverage_trace(e)
    res = {"t1_enter": api.attempt(lambda: t1.__enter__() is t1)}
    ready, go = threading.Event(), threading.Event()

    def other():
        t2 = api.coverage_trace(e2)
        res["t2_enter"] = api.attempt(lambda: t2.__enter__() is t2)
        ready.set()
        go.wait(10)
        res["t2_exit"] = api.attempt(lambda: bool(t2.__exit__(None, None, None)))
        res["t2_record"] = api.record(t2)
    th = threading.Thread(target=other)
    th.start()
    ready.wait(10)
    res["t1_exit"] = api.attempt(lambda: bool(t1.__exit__(None, None, None)))
    res["t1_record"] = api.record(t1)
    go.set()
    th.join(10)
    out["e"] = res
    out["e_hooks"] = hooks()
    return out
