"""round3_module/t05_close_cost.py and t11_perf_closure.py, rewritten: their measured costs (section close on a
large heap; per-call overhead for plain, closure and many-local functions) are timings, not spec-fixed
observables; the rewrite runs the same programs at reduced size and records their outcomes: 20 per-item sections
calling two declared targets with 300 000 extra tracked objects (the repro's argv size), and 20 000 calls each
of plain/clos/bigloc in one section (the repro's 200 000)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r3m_fx import PERF, SIMPLE


def main(api):
    fs, m = api.fixture("rp_fx_simple", SIMPLE), api.fixture("rp_fx3_perf", PERF)
    keep = [[i] for i in range(300_000)]
    e = api.exp({"G": ["rp_fx_simple:f", "rp_fx_simple:g"]})

    def items(c):
        for _ in range(20):
            c.run("G", lambda: (fs.f(), fs.g()))
    out = {"t05_close_on_heap": api.trace(e, items)}
    del keep
    e = api.exp({"G": ["rp_fx3_perf:plain", "rp_fx3_perf:clos", "rp_fx3_perf:bigloc"]})

    def body():
        for k in ("plain", "clos", "bigloc"):
            fn = getattr(m, k)
            for i in range(20_000):
                fn(i)
    out["t11_per_call"] = api.trace(e, lambda c: c.run("G", body))
    return out
