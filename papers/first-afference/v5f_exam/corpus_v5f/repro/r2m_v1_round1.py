"""round2_module/v1_round1.py, rewritten: round 1's items replayed (B1 factory closure and no-wraps decorator; B2
dataclass __init__; N2 inherited Sub.fit; B3 a pool job outliving A that calls g during B, the same with A
exiting by an exception, a thread started outside sections, an asyncio task created in A awaited in B; D1
non-LIFO exits, re-entry, a thread keeping a hook after exit). Waits are events, not sleeps."""
import asyncio, os, sys, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
from r1m_fx import SIMPLE

FACTORY = '''
def _make(k):
    def check(x):
        return x > k
    return check
check_low = _make(0.1)
check_high = _make(0.9)
def plain(f):
    def inner(*a, **k):
        return f(*a, **k)
    return inner
@plain
def entry_a(): return "a"
@plain
def entry_b(): return "b"
'''
DC = '''
from dataclasses import dataclass
@dataclass
class NullModel:
    n: int
    seed: int = 0
@dataclass
class AltModel:
    n: int
    seed: int = 0
class Base:
    def fit(self): return 1
class Sub(Base): pass
class Other(Base): pass
'''


def main(api):
    fx, dc, fs = api.fixture("rp_fx_factory", FACTORY), api.fixture("rp_fx_dc", DC), api.fixture("rp_fx_simple", SIMPLE)
    out = {"B1_factory": api.trace(api.exp({"G": ["rp_fx_factory:check_high"]}), lambda c: c.run("G", fx.check_low, 0.5)),
           "B1_no_wraps": api.trace(api.exp({"G": ["rp_fx_factory:entry_b"]}), lambda c: c.run("G", fx.entry_a)),
           "B2_dataclass": api.trace(api.exp({"G": ["rp_fx_dc:NullModel.__init__"]}), lambda c: c.run("G", dc.AltModel, 3)),
           "N2_inherited": api.trace(api.exp({"G": ["rp_fx_dc:Sub.fit"]}), lambda c: c.run("G", lambda: dc.Other().fit()))}
    E2 = lambda: api.exp({"A": ["rp_fx_simple:f"], "B": ["rp_fx_simple:g"]}, sections={"A": "A", "B": "B"})
    for variant in ("returns", "raises"):
        ev, done, pool = threading.Event(), threading.Event(), ThreadPoolExecutor(1)

        def a():
            fs.f()
            pool.submit(fs.slow_then_g, 0, ev).add_done_callback(lambda _f: done.set())
            if variant == "raises":
                raise ValueError("expected refusal")

        def b():
            ev.set()
            done.wait(10)
        out[f"B3_outlives_A_{variant}"] = api.trace(E2(), lambda c: c.run("A", a), lambda c: c.run("B", b))
        pool.shutdown(wait=True)
    ev2, th = threading.Event(), []

    def start(c):
        t = threading.Thread(target=fs.slow_then_g, args=(0, ev2))
        t.start()
        th.append(t)

    def b2():
        ev2.set()
        th[0].join(10)
    out["B3_thread_outside"] = api.trace(api.exp({"B": ["rp_fx_simple:g"]}, sections={"B": "B"}), start, lambda c: c.run("B", b2))
    box = {}

    async def a3():
        fs.g()
        box["t"] = asyncio.ensure_future(fs.af())

    async def b3():
        return await box["t"]

    async def drive(c):
        await c.run_async("A", a3)
        await c.run_async("B", b3)
    e = api.exp({"B": ["rp_fx_simple:f"], "A": ["rp_fx_simple:g"]}, sections={"A": "A", "B": "B"})
    out["B3_asyncio_task_A_to_B"] = api.trace(e, lambda c: asyncio.run(drive(c)))
    e, e2 = api.exp({"G": ["rp_fx_simple:f"]}), api.exp({"H": ["rp_fx_simple:g"]})
    t1, t2 = api.coverage_trace(e), api.coverage_trace(e2)
    out["D1_non_lifo"] = [api.attempt(lambda: t1.__enter__() is t1), api.attempt(lambda: t2.__enter__() is t2),
                          api.attempt(lambda: bool(t1.__exit__(None, None, None))),
                          api.attempt(lambda: bool(t2.__exit__(None, None, None))),
                          sys.getprofile() is None, threading.getprofile() is None]
    cov = api.coverage_trace(e)
    def reent():
        with cov:
            with cov:
                pass
    out["D1_reentry"] = [api.attempt(reent), api.record(cov)]
    go, ev3, seen, th = threading.Event(), threading.Event(), {}, []

    def worker():
        go.wait(10)
        fs.f()
        seen["profile_none"] = sys.getprofile() is None
        ev3.set()

    def st(c):
        t = threading.Thread(target=worker)
        t.start()
        th.append(t)
    keep = []
    out["D1_thread_keeps_hook"] = api.trace(e, st, keep=keep)
    go.set()
    ev3.wait(10)
    th[0].join(10)
    out["D1_after"] = {"record": api.record(keep[0]), **seen}
    return out
