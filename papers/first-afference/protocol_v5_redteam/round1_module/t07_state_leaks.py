from rtlib import *
import fx_simple as fx, sys, threading, contextlib
e = exp(spec(G={"exercises": ["fx_simple:f"]}))
e2 = exp(spec(H={"exercises": ["fx_simple:g"]}))

# (a) two tracers exited out of LIFO order (e.g. held in a dict / ExitStack misuse / generator ctx)
t1, t2 = coverage_trace(e), coverage_trace(e2)
t1.__enter__(); t2.__enter__()
t1.__exit__(None, None, None); t2.__exit__(None, None, None)
print("(a) after both exited: sys.getprofile() =", sys.getprofile(),
      "| threading.getprofile() =", threading.getprofile())
sys.setprofile(None); threading.setprofile(None)

# (b) the same tracer re-entered (nested with cov: with cov:)
cov = coverage_trace(e)
with cov:
    with cov:
        pass
    with cov.section("G"):
        fx.f()               # really called inside the section, inside the outer `with cov`
print("(b) re-entered tracer:", score(e, cov.record()))
print("    after exit: sys.getprofile() =", sys.getprofile())
sys.setprofile(None); threading.setprofile(None)

# (c) exception inside the section: profiler restored?
try:
    with coverage_trace(e) as cov:
        with cov.section("G"):
            fx.f(); raise RuntimeError("boom")
except RuntimeError: pass
print("(c) after exception: sys.getprofile() =", sys.getprofile(), threading.getprofile())

# (d) a thread started during the trace keeps the hook after exit and chains forever
seen = []
def pre(frame, event, arg): seen.append(event)
ev = threading.Event(); go = threading.Event()
def worker():
    go.wait(); fx.f(); ev.set()
with coverage_trace(e) as cov:
    th = threading.Thread(target=worker); th.start()
go.set(); ev.wait(); th.join()
print("(d) post-exit calls counted:", cov.record()["unsectioned"])
