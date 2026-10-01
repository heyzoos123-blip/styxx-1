"""round3_exam/probe/ (bound.py, hook_failed.py, probes.py, sib.py, thread_start.py; fixtures pfx*.py), rewritten
(round3_exam/ falls in the text's range "round1_module/ through round4/", see SPEC_GAPS.md, Revision 13
follow-ups). bound: a declared bound method of a module-level instance; hook_failed / probe 1: a RecursionError
inside the section after the target ran; probe 3 / thread_start: threading:Thread.start declared; probe 4: a
runtime wraps sibling kept alive past the close, only it called; probe 5 / 5b: a dead uncollected cyclic sibling
made in the section and before the trace; probe 6: cProfile enabled and disabled inside the section (v5e's
threading.setprofile check is private; here threading.getprofile() and sys.getprofile() after); probe 6b: a foreign
Python profiler installed before the exit; probe 7: check_metrics on a non-dict; probe 8: two concurrently open
sections sharing a one-worker pool, B's pooled job; sib: wraps siblings. Probe 2 (a section context manager closed
in a copied context) is not applicable: v5f's sections are calls (NOT_APPLICABLE.json)."""
import functools, gc, sys, threading
from concurrent.futures import ThreadPoolExecutor

PFX = ("import functools\ndef target(): return 1\ndef _run2(): return 12\n@functools.wraps(_run2)\ndef run_only(): return _run2()\n"
       "def _timed(fn):\n    def inner(*a, **k): return fn(*a, **k)\n    return inner\ndef _impl(): return 10\n"
       "score_all = _timed(_impl)\ndef cheap(): return 11\n"
       "def rec(n):\n    target()\n    return rec(n + 1)\n")
PFX2 = "class Base:\n    def fit(self): return 8\nclass Sub(Base): pass\nclass Other(Base): pass\nbound_fit = Sub().fit\n"
PFX3 = ("import functools\ndef _run(): return 12\n@functools.wraps(_run)\ndef run_fast(): return _run()\n"
        "@functools.wraps(_run)\ndef run_safe(): return _run()\n")


def main(api):
    pfx, pfx2, pfx3 = api.fixture("rp_pfx", PFX), api.fixture("rp_pfx2", PFX2), api.fixture("rp_pfx3", PFX3)
    out = {}
    T = lambda gates, *steps: api.trace(api.exp(gates), *steps)
    out["bound"] = T({"G": ["rp_pfx2:bound_fit"]}, lambda c: c.run("G", lambda: pfx2.Other().fit()))

    def hf():
        pfx.target()
        try:
            pfx.rec(0)
        except RecursionError:
            pass
    r = T({"G": ["rp_pfx:target"]}, lambda c: c.run("G", hf))
    # the count of target calls before the RecursionError depends on how deep the implementation's own frames
    # put the section body, which is not a spec-fixed observable; it is reduced to "at least one"
    for ops in (r.get("record") or {}).get("sections", {}).values():
        for o in ops:
            o["calls"] = {k: min(v, 1) for k, v in o["calls"].items()}
    if isinstance(r.get("score"), dict) and isinstance(r["score"].get("coverage"), dict):
        r["score"]["coverage"] = {g: {k: min(v, 1) for k, v in c.items()} for g, c in r["score"]["coverage"].items()}
    out["hook_failed"] = r

    def tstart():
        t = threading.Thread(target=lambda: None)
        t.start()
        t.join()
    out["thread_start"] = T({"G": ["threading:Thread.start"]}, lambda c: c.run("G", tstart))
    keep = []

    def wc():
        def sib2():
            return pfx._run2()
        functools.wraps(pfx._run2)(sib2)
        keep.append(sib2)
        sib2()
    out["wraps_sibling_at_close"] = T({"G": ["rp_pfx:run_only"]}, lambda c: c.run("G", wc))
    keep.clear()

    def gcc():
        pfx.score_all()
        gc.disable()
        w = pfx._timed(pfx.cheap)
        w.me = w
        del w
    try:
        out["gc_before_close"] = T({"G": ["rp_pfx:score_all"]}, lambda c: c.run("G", gcc))
    finally:
        gc.enable()
    gc.disable()
    try:
        w = pfx._timed(pfx.cheap)
        w.me = w
        del w
        out["gc_before_entry"] = T({"G": ["rp_pfx:score_all"]}, lambda c: c.run("G", pfx.score_all))
    finally:
        gc.enable()
    import cProfile

    def cp():
        pr = cProfile.Profile()
        pr.enable()
        pfx.target()
        pr.disable()
    out["cprofile_in_section"] = T({"G": ["rp_pfx:target"]}, lambda c: c.run("G", cp))
    out["cprofile_in_section_hooks"] = {"sys": sys.getprofile() is None, "threading": threading.getprofile() is None}
    e = api.exp({"G": ["rp_pfx:target"]})
    t = api.coverage_trace(e)
    t.__enter__()
    sys.setprofile(lambda *a: None)
    try:
        out["foreign_profiler_at_exit"] = api.attempt(lambda: bool(t.__exit__(None, None, None)))
    finally:
        sys.setprofile(None)
    out["foreign_profiler_at_exit_record"] = api.record(t)
    out["foreign_profiler_at_exit_threading_none"] = threading.getprofile() is None
    out["check_metrics_non_dict"] = api.metrics(e, [{"m": 1.0}])

    def ambig(c):
        pool = ThreadPoolExecutor(max_workers=1)
        b1, b2 = threading.Barrier(2, timeout=20), threading.Barrier(2, timeout=20)

        def ra():
            c.run("A", lambda: (pool.submit(pfx.cheap).result(), b1.wait(), b2.wait(), pool.shutdown(wait=True)) and None)

        def rb():
            c.run("B", lambda: (b1.wait(), pool.submit(pfx.target).result(), b2.wait()) and None)
        ts = [threading.Thread(target=ra), threading.Thread(target=rb)]
        [x.start() for x in ts]
        [x.join(30) for x in ts]
    out["ambiguous_B"] = T({"B": ["rp_pfx:target"], "A": ["rp_pfx:cheap"]}, ambig)
    out["sib"] = T({"G": ["rp_pfx3:run_fast"]}, lambda c: c.run("G", pfx3.run_safe))
    return out
