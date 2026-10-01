"""round1_module/t04_thread_leak_section.py, rewritten: (1) section A's work starts a pool job that calls g while
section B runs (B never calls g; the job waits on an event B sets, so it runs during B, not by a sleep); (2) a
thread started before any section calls g while section B runs."""
import os, sys, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
from r1m_fx import SIMPLE


def main(api):
    fx = api.fixture("rp_fx_simple", SIMPLE)
    out = {}
    e = api.exp({"A": ["rp_fx_simple:f"], "B": ["rp_fx_simple:g"]}, sections={"A": "A", "B": "B"})
    ev, done, pool = threading.Event(), threading.Event(), ThreadPoolExecutor(1)

    def a():
        fx.f()
        fut = pool.submit(fx.slow_then_g, 0, ev)
        fut.add_done_callback(lambda _f: done.set())

    def b():
        ev.set()
        done.wait(10)
    out["thread_outlives_section"] = api.trace(e, lambda c: c.run("A", a), lambda c: c.run("B", b))
    pool.shutdown(wait=True)
    e = api.exp({"B": ["rp_fx_simple:g"]}, sections={"B": "B"})
    ev2 = threading.Event()
    th = []

    def start(c):
        t = threading.Thread(target=fx.slow_then_g, args=(0, ev2))
        t.start()
        th.append(t)

    def b2():
        ev2.set()
        th[0].join(10)
    out["thread_started_outside_section"] = api.trace(e, start, lambda c: c.run("B", b2))
    return out
