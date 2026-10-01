"""round2_module/a9_threadpool_race.py, rewritten: multiprocessing.pool.ThreadPool used as a context manager
inside the section (its __exit__ terminates the pool), three runs; and a concurrent.futures pool as control."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
from r2m_fx import SIMPLE


def main(api):
    from multiprocessing.pool import ThreadPool
    fs = api.fixture("rp_fx_simple", SIMPLE)
    out = {}

    def mp():
        with ThreadPool(4) as p:
            p.map(lambda _: fs.f(), range(8))

    def cfp():
        with ThreadPoolExecutor(4) as p:
            list(p.map(lambda _: fs.f(), range(8)))
    for i in range(3):
        out[f"mp_threadpool_{i}"] = api.trace(api.exp({"G": ["rp_fx_simple:f"]}), lambda c: c.run("G", mp))
    out["cf_pool"] = api.trace(api.exp({"G": ["rp_fx_simple:f"]}), lambda c: c.run("G", cfp))
    return out
