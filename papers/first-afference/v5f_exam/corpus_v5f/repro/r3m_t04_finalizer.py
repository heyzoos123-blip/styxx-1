"""round3_module/t04_finalizer_deadlock.py and t04b_finalizer_deadlock_natural.py, rewritten: cyclic garbage
whose finalizer calls the declared target. t04: the gen-0 threshold swept over k = 1..10 so a collection lands at
each allocation in turn, (i) during the trace's exit, (ii) during record() after the exit, (iii) during a section (cov.run); the repro ran one
(where, k) per process under faulthandler's 5 s exit, here every pair runs in this process and a deadlock is the
corpus run's timeout. t04b: default thresholds, 5000 per-item sections (the repro's 20000) each leaving such
garbage."""
import gc, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r3m_fx import SIMPLE


def main(api):
    fs = api.fixture("rp_fx_simple", SIMPLE)

    class Res:
        def __init__(self):
            self.me = self

        def __del__(self):
            fs.f()
    out = {}
    old = gc.get_threshold()
    try:
        for where in ("exit", "record", "run"):
            for k in range(1, 11):
                e = api.exp({"G": ["rp_fx_simple:f"]})
                cov = api.coverage_trace(e)
                r = {}

                def arm():
                    gc.collect()
                    gc.disable()
                    for _ in range(5):
                        Res()
                    gc.set_threshold(k)
                    gc.enable()
                try:
                    with cov:
                        if where != "run":
                            cov.run("G", fs.f)
                        if where == "exit":
                            arm()
                        if where == "run":
                            arm()
                            r["run"] = api.attempt(cov.run, "G", fs.f)
                            gc.set_threshold(*old)
                except BaseException as ex:            # noqa: BLE001
                    r["with"] = type(ex).__name__
                gc.set_threshold(*old)
                if where == "record":
                    arm()
                    r["record"] = api.record(cov)
                    gc.set_threshold(*old)
                r["final"] = api.record(cov)
                out[f"t04_{where}_{k}"] = r
    finally:
        gc.set_threshold(*old)
        gc.enable()
    gc.collect()

    class Res2:
        def __init__(self):
            self.me = self
            self.buf = [{} for _ in range(3)]

        def __del__(self):
            fs.f()

    def items(c):
        for _ in range(5000):
            c.run("G", lambda: (Res2(), fs.f()))
    keep = []
    res = api.trace(api.exp({"G": ["rp_fx_simple:f"]}), items, keep=keep)
    rec = keep[0].record() if keep else None
    out["t04b"] = {"steps": res.get("steps"), "exit": res.get("exit"),
                   "openings": len((rec or {}).get("sections", {}).get("G", [])),
                   "ends": sorted({o.get("end") for o in (rec or {}).get("sections", {}).get("G", [])}),
                   "problems": res.get("record", {}).get("problems") if isinstance(res.get("record"), dict) else None}
    gc.collect()
    return out
