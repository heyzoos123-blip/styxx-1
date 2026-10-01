"""round1_module/t05_false_refusals.py, rewritten: (a) a warm executor whose worker predates the trace runs the
declared function for the section; (b) two gates' sections run in parallel threads (a barrier starts both);
(c) the section's body enables and disables its own cProfile.Profile; the profiler after exit."""
import os, sys, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
from r1m_fx import SIMPLE


def main(api):
    import cProfile
    fx = api.fixture("rp_fx_simple", SIMPLE)
    out = {}
    e = api.exp({"G": ["rp_fx_simple:f"]})
    pool = ThreadPoolExecutor(1)
    pool.submit(lambda: None).result()
    out["a_warm_pool"] = api.trace(e, lambda c: c.run("G", lambda: pool.submit(fx.f).result()))
    pool.shutdown(wait=True)
    e2 = api.exp({"A": ["rp_fx_simple:f"], "B": ["rp_fx_simple:g"]}, sections={"A": "A", "B": "B"})
    errs = []

    def par(c):
        bar = threading.Barrier(2)

        def run(name, fn):
            try:
                bar.wait()
                c.run(name, fn)
            except BaseException as ex:            # noqa: BLE001
                errs.append(type(ex).__name__)
        ts = [threading.Thread(target=run, args=a) for a in (("A", fx.f), ("B", fx.g))]
        [t.start() for t in ts]
        [t.join() for t in ts]
    out["b_parallel_sections"] = api.trace(e2, par)
    out["b_errors"] = sorted(errs)

    def prof():
        pr = cProfile.Profile()
        pr.enable()
        fx.f()
        pr.disable()
    out["c_cprofile_inside"] = api.trace(e, lambda c: c.run("G", prof))
    out["c_profiler_after"] = sys.getprofile() is None
    return out
