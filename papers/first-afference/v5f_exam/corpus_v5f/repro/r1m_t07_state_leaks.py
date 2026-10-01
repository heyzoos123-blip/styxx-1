"""round1_module/t07_state_leaks.py, rewritten: (a) two tracers exited out of LIFO order; (b) the same tracer
re-entered, then a section run inside the outer enter; (c) an exception inside the section; (d) a thread started
during the trace calls the declared function after the exit. Each part records the profiler and trace-function
identity after it, and _v5_state()."""
import sys, threading


def main(api):
    fx = api.fixture("rp_fx_simple", 'def f(): return 1\ndef g(): return 2\n')
    hooks = lambda: {"getprofile_none": sys.getprofile() is None, "gettrace_none": sys.gettrace() is None,
                     "threading_getprofile_none": threading.getprofile() is None}
    out = {}
    e = api.exp({"G": ["rp_fx_simple:f"]})
    e2 = api.exp({"H": ["rp_fx_simple:g"]})
    t1, t2 = api.coverage_trace(e), api.coverage_trace(e2)
    out["a"] = [api.attempt(t1.__enter__), api.attempt(t2.__enter__),
                api.attempt(lambda: bool(t1.__exit__(None, None, None))), api.attempt(lambda: bool(t2.__exit__(None, None, None)))]
    out["a_records"] = [api.record(t1), api.record(t2)]
    out["a_hooks"], out["a_state"] = hooks(), api.state()
    cov = api.coverage_trace(e)
    steps = []
    try:
        with cov:
            steps.append(api.attempt(lambda: cov.__enter__()))
            steps.append(api.attempt(lambda: bool(cov.__exit__(None, None, None))))
            steps.append(api.attempt(cov.run, "G", fx.f))
    except BaseException as ex:                        # noqa: BLE001
        steps.append({"outer": type(ex).__name__})
    out["b"] = steps
    out["b_record"] = api.record(cov)
    try:
        out["b_score"] = api.score(e, cov.record())
    except BaseException as ex:                        # noqa: BLE001
        out["b_score"] = {"record": type(ex).__name__}
    out["b_hooks"], out["b_state"] = hooks(), api.state()

    def boom():
        fx.f()
        raise RuntimeError("boom")
    out["c"] = api.trace(e, lambda c: c.run("G", boom))
    out["c_hooks"], out["c_state"] = hooks(), api.state()
    ev, done = threading.Event(), threading.Event()

    def worker():
        ev.wait(10)
        fx.f()
        done.set()
    th = []

    def start(c):
        t = threading.Thread(target=worker)
        t.start()
        th.append(t)
    keep = []
    out["d"] = api.trace(e, start, keep=keep)
    ev.set()
    done.wait(10)
    th[0].join(10)
    out["d_record_after_post_exit_call"] = api.record(keep[0])
    out["d_hooks"], out["d_state"] = hooks(), api.state()
    return out
