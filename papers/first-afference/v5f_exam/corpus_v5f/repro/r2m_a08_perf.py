"""round2_module/a8_perf.py, rewritten: coverage_trace() construction for 40 declared targets with and without a
large population of gc-tracked objects. The repro measured construction time, which is not a spec-fixed
observable; the rewrite records the construction and enter outcome only (with 300 000 tracked objects, not the
repro's 3 000 000, to bound the corpus's memory)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r2m_fx import MANY


def main(api):
    api.fixture("rp_fx2_many", MANY)
    e = api.exp({"G": [f"rp_fx2_many:t{i}" for i in range(40)]})
    out = {}
    for heap in (0, 300_000):
        junk = [[i] for i in range(heap)]
        out[f"heap_{heap}"] = api.trace(e)
        del junk
    return out
