"""Probes of round-3 repairs the frozen exam does not exercise. Each prints PROBE name: OK/BROKEN detail."""
import sys, gc, functools, threading, types
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import *
import pfx
from styxx.protocol import _thread_profile

def run(name, fn, want):
    before_s, before_t = sys.getprofile(), _thread_profile()
    try:
        got = fn()
    except GateSpecError as e:
        got = "refused " + str(e)[:60]
    except Exception as e:
        got = f"crash {type(e).__name__}: {str(e)[:80]}"
    sys.setprofile(before_s); threading.setprofile(before_t)
    ok = got.startswith(want)
    print(f"PROBE {name}: {'OK' if ok else 'BROKEN'} want={want!r} got={got[:110]!r}", flush=True)

def traced(gates, body, edit=None):
    e = exp_of(gates)
    with coverage_trace(e) as cov:
        body(cov)
    r = {"m": 1.0, "coverage_trace": cov.record()}
    return "scored " + e.score(r).verdict + " " + str(r["coverage_trace"]["sections"])

# 1 HOOK_FAILED: an exception inside the hook body (RecursionError in _on_call)
def hook_failed():
    exec("def rec(n):\n    target()\n    return rec(n+1)\n", pfx.__dict__)
    def body(cov):
        with cov.section("G"):
            pfx.target()
            try: pfx.rec(0)
            except RecursionError: pass
    return traced({"G": {"exercises": ["pfx:target"]}}, body)
run("hook_failed_refuses", hook_failed, "refused [V5:HOOK_FAILED]")

# 2 close_refusals recorded
def close_ref():
    e = exp_of({"G": {"exercises": ["pfx:target"]}})
    cov = coverage_trace(e)
    try:
        with cov:
            cm = cov.section("G"); cm.__enter__(); pfx.target()
            import contextvars
            contextvars.copy_context().run(cm.__exit__, None, None, None)
    except GateSpecError:
        pass
    cr = cov.record()["close_refusals"]
    return "recorded " + cr[0][:30] if cr else "not recorded"
run("close_refusals_recorded", close_ref, "recorded [V5:SECTION_CONTEXT]")

# 3 Thread.start declarable
def tstart():
    def body(cov):
        with cov.section("G"):
            t = threading.Thread(target=lambda: None); t.start(); t.join()
    return traced({"G": {"exercises": ["threading:Thread.start"]}}, body)
run("thread_start_declarable", tstart, "scored PASS {'G': {'threading:Thread.start': 1}}")

# 4 wraps sibling created at runtime, kept alive past close, only it is called
keep = []
def wraps_close():
    def body(cov):
        try:
            with cov.section("G"):
                sib = functools.wraps(pfx._run2)(lambda: pfx._run2())
                def sib2(): return pfx._run2()
                functools.wraps(pfx._run2)(sib2)
                keep.append(sib2); sib2()
        finally:
            pass
    try:
        return traced({"G": {"exercises": ["pfx:run_only"]}}, body)
    finally:
        keep.clear()
run("wraps_sibling_at_close", wraps_close, "refused [V5:SHARED_CODE]")

# 5 gc at close: a dead cyclic clone of the declared code must not count as a holder
def gc_close():
    def body(cov):
        with cov.section("G"):
            pfx.score_all()
            gc.disable()
            w = pfx._timed(pfx.cheap); w.me = w; del w      # dead, uncollected, cyclic
    try:
        return traced({"G": {"exercises": ["pfx:score_all"]}}, body)
    finally:
        gc.enable()
run("gc_before_close_recount", gc_close, "scored PASS")

# 5b gc at entry
def gc_entry():
    gc.disable()
    try:
        w = pfx._timed(pfx.cheap); w.me = w; del w
        def body(cov):
            with cov.section("G"):
                pfx.score_all()
        return traced({"G": {"exercises": ["pfx:score_all"]}}, body)
    finally:
        gc.enable()
run("gc_before_entry_count", gc_entry, "scored PASS")

# 6 threading hook reset on a refusal exit path
def thr_on_error():
    import cProfile
    before = _thread_profile()
    e = exp_of({"G": {"exercises": ["pfx:target"]}})
    try:
        with coverage_trace(e) as cov:
            with cov.section("G"):
                pr = cProfile.Profile(); pr.enable(); pfx.target(); pr.disable()
    except GateSpecError as ex:
        msg = str(ex)[:30]
    return ("restored " if _thread_profile() is before else "LEAKED thread hook ") + msg
run("thread_hook_reset_on_refusal", thr_on_error, "restored [V5:PROFILER_REPLACED]")

# 6b threading hook reset on the EXIT_ORDER path: tracer A exits while a foreign Python profiler is on sys
def thr_on_exit_order():
    before = _thread_profile()
    e = exp_of({"G": {"exercises": ["pfx:target"]}})
    t = coverage_trace(e); t.__enter__()
    sys.setprofile(lambda *a: None)
    try:
        t.__exit__(None, None, None); msg = "no refusal"
    except GateSpecError as ex:
        msg = str(ex)[:24]
    return ("restored " if _thread_profile() is before else "LEAKED thread hook ") + msg
run("thread_hook_reset_on_exit_order", thr_on_exit_order, "restored [V5:EXIT_ORDER]")

# 7 check_metrics on a non-dict reports something unusable
def cm_nondict():
    e = exp_of({"G": {"exercises": ["pfx:target"]}})
    out = e.check_metrics([{"m": 1.0}])
    bad = [k for k, v in out.items() if not v["usable"]]
    return f"report unusable={sorted(bad)}" if bad else f"report says all usable/empty: {out}"
run("check_metrics_non_dict_content", cm_nondict, "report unusable=['G', 'G:exercises']")

# 8 ambiguous: thread-inherited work while two sections open counts for NEITHER (B side)
def ambig_b():
    from concurrent.futures import ThreadPoolExecutor
    def body(cov):
        pool = ThreadPoolExecutor(max_workers=1)
        b1, b2 = threading.Barrier(2, timeout=20), threading.Barrier(2, timeout=20)
        def ra():
            with cov.section("A"):
                pool.submit(pfx.cheap).result(); b1.wait(); b2.wait(); pool.shutdown(wait=True)
        def rb():
            with cov.section("B"):
                b1.wait(); pool.submit(pfx.target).result(); b2.wait()
        ts = [threading.Thread(target=ra), threading.Thread(target=rb)]
        [t.start() for t in ts]; [t.join(30) for t in ts]
    return traced({"B": {"exercises": ["pfx:target"]}, "A": {"exercises": ["pfx:cheap"]}}, body)
run("ambiguous_not_credited_to_B", ambig_b, "refused [V5:NOT_EXERCISED] gate 'B'")
