"""round2_module/a11_grandchild.py, rewritten: section A calls f, starts a child thread and raises; the child,
released while section B runs, starts a grandchild that calls g; B waits for it."""
import os, sys, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r2m_fx import SIMPLE


def main(api):
    fs = api.fixture("rp_fx_simple", SIMPLE)
    e = api.exp({"A": ["rp_fx_simple:f"], "B": ["rp_fx_simple:g"]}, sections={"A": "A", "B": "B"})
    go, done, th = threading.Event(), threading.Event(), []

    def child():
        go.wait(10)
        t2 = threading.Thread(target=fs.g)
        t2.start()
        t2.join()
        done.set()

    def a():
        fs.f()
        t1 = threading.Thread(target=child)
        t1.start()
        th.append(t1)
        raise ValueError("expected")

    def b():
        go.set()
        done.wait(10)
    res = api.trace(e, lambda c: c.run("A", a), lambda c: c.run("B", b))
    th[0].join(10)
    return {"grandchild": res}
