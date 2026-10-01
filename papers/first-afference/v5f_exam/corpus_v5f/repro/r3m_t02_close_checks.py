"""round3_module/t02_close_checks_bypassed.py, rewritten: a a clone of the declared code alive at close, the
section exited by an exception; b per-item sections each calling a fresh clone, every refusal swallowed by a
generic try/except; c a runtime wraps sibling alive at close, its refusal swallowed; d a thread started in an
exception-exited section calls the declared function during a later opening of the same section (released by an
event the later opening sets)."""
import os, sys, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r3m_fx import CLONE, SIMPLE, WRAPS


def main(api):
    c, w, fs = api.fixture("rp_fx3_clone", CLONE), api.fixture("rp_fx3_wraps", WRAPS), api.fixture("rp_fx_simple", SIMPLE)
    out = {}
    E = lambda t: api.exp({"G": [t]})

    def a():
        c.make_variant()(1)
        raise TimeoutError("battery item timed out")
    c.REGISTRY.clear()
    out["a_clone_alive_exception_exit"] = api.trace(E("rp_fx3_clone:target"), lambda cov: cov.run("G", a))
    out["a_registry"] = len(c.REGISTRY)
    c.REGISTRY.clear()
    errors = []

    def items(cov):
        for item in range(3):
            try:
                cov.run("G", lambda: c.make_variant()(item))
            except Exception as ex:                    # noqa: BLE001
                errors.append(type(ex).__name__)
    out["b_swallowed_per_item"] = api.trace(E("rp_fx3_clone:target"), items)
    out["b_errors"] = errors
    keep = []

    def cc(cov):
        try:
            def body():
                h = w.retrying(w._core)
                keep.append(h)
                return h(1)
            cov.run("G", body)
        except Exception as ex:                        # noqa: BLE001
            errors.append(type(ex).__name__)
    out["c_wraps_sibling_alive"] = api.trace(E("rp_fx3_wraps:public"), cc)
    ev, th = threading.Event(), []

    def d1():
        t = threading.Thread(target=lambda: (ev.wait(10), fs.f()))
        t.start()
        th.append(t)
        raise RuntimeError("abort item")

    def d(cov):
        try:
            cov.run("G", d1)
        except RuntimeError:
            pass

    def d2():
        ev.set()
        th[0].join(10)
    out["d_thread_outlives_into_later_opening"] = api.trace(E("rp_fx_simple:f"), d, lambda cov: cov.run("G", d2))
    return out
