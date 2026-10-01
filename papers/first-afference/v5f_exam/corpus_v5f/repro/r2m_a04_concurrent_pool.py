"""round2_module/a4_concurrent_pool_falsepass.py, rewritten: gates A and B run concurrently in two runner threads
started outside any section and share one single-worker pool spawned by A's first submit. A submits g only and
waits; B calls g directly and f through the pool."""
import os, sys, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
from r2m_fx import SIMPLE


def main(api):
    fs = api.fixture("rp_fx_simple", SIMPLE)
    errs = []

    def run(c):
        pool = ThreadPoolExecutor(1)
        a_submitted, pool_down = threading.Event(), threading.Event()

        def gate_a():
            try:
                c.run("A", lambda: (pool.submit(fs.g).result(), a_submitted.set(), pool_down.wait(10)))
            except BaseException as ex:                # noqa: BLE001
                errs.append(type(ex).__name__)

        def gate_b():
            try:
                a_submitted.wait(10)
                c.run("B", lambda: (fs.g(), pool.submit(fs.f).result()))
            except BaseException as ex:                # noqa: BLE001
                errs.append(type(ex).__name__)
        ta, tb = threading.Thread(target=gate_a), threading.Thread(target=gate_b)
        ta.start()
        tb.start()
        tb.join(10)
        pool.shutdown(wait=True)
        pool_down.set()
        ta.join(10)
    e = api.exp({"A": ["rp_fx_simple:f"], "B": ["rp_fx_simple:g"]}, sections={"A": "A", "B": "B"})
    return {"concurrent_shared_pool": api.trace(e, run), "errors": sorted(errs)}
