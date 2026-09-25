# ---- self-contained prelude (identical in every script of this directory) ----
import json, os, subprocess, sys, tempfile, threading, types, importlib
from pathlib import Path
sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

def mkexp(**gates):
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, **extra} for n, extra in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"},
                                      {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "SMOKE"}
    td = Path(tempfile.mkdtemp(prefix="rt4ca_"))
    p = td / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True, capture_output=True)
    return Experiment(p)

def fixture(name, src):
    d = Path(tempfile.mkdtemp(prefix="rt4fx_"))
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    sys.path.insert(0, str(d))
    sys.modules.pop(name, None)
    return importlib.import_module(name)

def score(e, rec, m=1.0, **extra):
    try:
        v = e.score({"m": m, "coverage_trace": rec, **extra})
        return f"PASS verdict={v.verdict} coverage={v.coverage}"
    except GateSpecError as ex:
        return f"REFUSED {str(ex)[:160]}"

def clean():
    return (not (P._MINTED or P._BY_FN or P._ANCHORS or P._THREADS) and P._ACTIVE == 0
            and sys.getprofile() is None)
# ---- end prelude ----
# HELD battery: the original round-1..3 attacks rebuilt against v5e, plus 1-3 variants per closure row
# that change the one detail the closure argument relies on. Every line must show its expected outcome.
import asyncio, functools, marshal, copy, gc, time, signal, queue, concurrent.futures as cf, dataclasses
SRC = r'''
import functools, dataclasses, types, threading
def _make(k):
    def check(x=0): return x > k
    return check
check_low = _make(1); check_high = _make(9)
def deco_nowraps(fn):
    def inner(*a): return fn(*a)
    return inner
entry_a = deco_nowraps(lambda: 1); entry_b = deco_nowraps(lambda: 2)
def _timed(fn):
    def w(*a): return fn(*a)
    return w
score_all = _timed(lambda: 10)
def cheap_path(): return 11
def make_mul(k):
    return lambda x, k=k: x * k
double = make_mul(2)
def deco_wraps(fn):
    @functools.wraps(fn)
    def w(*a): return fn(*a)
    return w
def _run(x): return x
run_fast = deco_wraps(_run)
run_safe = deco_wraps(_run)
def run_plain(x): return _run(x)
@dataclasses.dataclass
class DA:
    x: int = 0
@dataclasses.dataclass
class DB:
    x: int = 0
class Base:
    def fit(self): return 1
class Sub(Base): pass
class Other(Base): pass
default_model = Sub()
def f(x=0): return x
def g(x=0): return x
def rec(n): return rec(n + 1)
@functools.singledispatch
def dispatch(x): return "obj"
@dispatch.register
def _(x: int): return "int"
def gen():
    yield 1
    yield 2
'''
fx = fixture("ca_held", SRC)
vend = fixture("ca_held_vendored", "def f(x=0): return x\n")
M = "ca_held"
rows = []
def case(row, expect):
    def deco(fn):
        try:
            got = fn()
        except GateSpecError as ex:
            got = f"REFUSED-AT-ENTRY {str(ex)[:70]}"
        except BaseException as ex:
            got = f"ESCAPED {type(ex).__name__}: {str(ex)[:60]}"
        leak = "" if clean() else f" [LEFTOVER _THREADS={dict(P._THREADS)} prof={sys.getprofile()}]"
        ok = got.startswith(expect) and not leak
        rows.append(ok)
        print(f"{'held' if ok else 'BROKE'} {row:58s} -> {got[:80]}{leak}")
        sys.setprofile(None); P._THREADS.clear()
        return fn
    return deco
def trace(targets, harness, sections=None):
    gates = {s: {"exercises": t, "section": s} for s, t in (sections or {"G": targets}).items()}
    e = mkexp(**gates)
    with coverage_trace(e) as cov:
        harness(cov)
    return e, cov.record()
def gate(e, rec, name):
    try:
        return f"PASS {e._check_coverage(name, {'m': 1.0, 'coverage_trace': rec})}"
    except GateSpecError as ex:
        return f"REFUSED {str(ex)[:160]}"
def one(targets, harness, gate="G"):
    e, rec = trace(targets, harness)
    return score(e, rec)

# R1-B1 shared code object
@case("R1-B1 factory sibling: declare check_low, call check_high", "REFUSED [V5:NOT_EXERCISED]")
def _(): return one([f"{M}:check_low"], lambda c: c.run("G", fx.check_high, 5))
@case("R1-B1 v: sibling built by the factory DURING the trace", "REFUSED [V5:NOT_EXERCISED]")
def _(): return one([f"{M}:check_low"], lambda c: c.run("G", lambda: fx._make(1)(5)))
@case("R1-B1 no-wraps decorator sibling: declare entry_a, call entry_b", "REFUSED [V5:NOT_EXERCISED]")
def _(): return one([f"{M}:entry_a"], lambda c: c.run("G", fx.entry_b))
@case("R1-B1 v: declare both siblings, call one: other not credited", "REFUSED [V5:NOT_EXERCISED]")
def _(): return one([f"{M}:check_low", f"{M}:check_high"], lambda c: c.run("G", fx.check_low, 1))
# R1-B2 equality not identity
@case("R1-B2 vendored equal copy in another module", "REFUSED [V5:NOT_EXERCISED]")
def _(): return one([f"{M}:f"], lambda c: c.run("G", vend.f, 1))
@case("R1-B2 v: marshal round-trip clone made in the trace, same globals", "REFUSED [V5:NOT_EXERCISED]")
def _(): return one([f"{M}:f"], lambda c: c.run("G", lambda: types.FunctionType(
    marshal.loads(marshal.dumps(fx.f.__code__)), fx.f.__globals__)(1)))
@case("R1-B2 dataclass DB() for DA.__init__", "REFUSED [V5:NOT_EXERCISED]")
def _(): return one([f"{M}:DA.__init__"], lambda c: c.run("G", fx.DB))
@case("R1-B2 v: copy.deepcopy(f) is f (atomic) -> credited", "PASS")
def _(): return one([f"{M}:f"], lambda c: c.run("G", copy.deepcopy(fx.f), 1))
# R1-B3 global section slot
def thread_in_A_calls_during_B(c):
    go, done = threading.Event(), threading.Event()
    def worker():
        go.wait(5); fx.f(1); done.set()
    def A():
        threading.Thread(target=worker).start()
    c.run("A", A)
    def B():
        go.set(); done.wait(5)
    c.run("B", B)
@case("R1-B3 thread started in A calls f while B is open (gate B)", "REFUSED [V5:NOT_EXERCISED]")
def _():
    e, rec = trace(None, thread_in_A_calls_during_B, {"A": [f"{M}:g"], "B": [f"{M}:f"]})
    return gate(e, rec, "B")
@case("R1-B3 v: asyncio task created in run_async A, awaited in B", "REFUSED [V5:NOT_EXERCISED]")
def _():
    def h(c):
        box = {}
        async def A():
            async def job(): fx.f(1)
            box["t"] = asyncio.get_running_loop().create_task(job())
        async def B(): await box["t"]
        async def main():
            await c.run_async("A", A); await c.run_async("B", B)
        asyncio.run(main())
    e, rec = trace(None, h, {"A": [f"{M}:g"], "B": [f"{M}:f"]})
    return gate(e, rec, "B")
@case("R1-B3 v: call_soon_threadsafe into a loop inside cov.run(A)", "REFUSED [V5:NOT_EXERCISED]")
def _():
    def h(c):
        def A():
            loop = asyncio.new_event_loop()
            def other(): loop.call_soon_threadsafe(fx.f, 1); loop.call_soon_threadsafe(loop.stop)
            threading.Thread(target=other).start(); loop.run_forever(); loop.close()
        c.run("A", A)
    return score(*trace(None, h, {"A": [f"{M}:f"]}))
@case("R1-B3 v: ThreadPoolExecutor job submitted from A (no own section)", "REFUSED [V5:NOT_EXERCISED]")
def _():
    def h(c):
        with cf.ThreadPoolExecutor(2) as ex:
            c.run("A", lambda: ex.submit(fx.f, 1).result())
    return score(*trace(None, h, {"A": [f"{M}:f"]}))
@case("R1-B3 v: threading.Timer started in A fires during A", "REFUSED [V5:NOT_EXERCISED]")
def _():
    def h(c):
        def A():
            t = threading.Timer(0.01, fx.f, (1,)); t.start(); t.join()
        c.run("A", A)
    return score(*trace(None, h, {"A": [f"{M}:f"]}))
# R1-B4 C profiler
@case("R1-B4 cProfile enabled before open", "REFUSED-AT-RUN [V5:FOREIGN_PROFILER]" if sys.version_info < (3, 12) else "PASS")
def _():
    import cProfile
    pr = cProfile.Profile(); pr.enable()
    try:
        e = mkexp(G={"exercises": [f"{M}:f"]})
        with coverage_trace(e) as c:
            try:
                c.run("G", fx.f, 1)
            except GateSpecError as ex:
                still = sys.getprofile() is pr if sys.version_info < (3, 12) else True
                return f"REFUSED-AT-RUN {str(ex)[:40]} profiler-still-installed={still}"
        return score(e, c.record())
    finally:
        pr.disable()
@case("R1-B4 v: pure-Python profiler present at open (left installed)", "REFUSED-AT-RUN [V5:FOREIGN_PROFILER]")
def _():
    p = lambda fr, ev, a: None
    sys.setprofile(p)
    try:
        e = mkexp(G={"exercises": [f"{M}:f"]})
        with coverage_trace(e) as c:
            try:
                c.run("G", fx.f, 1)
            except GateSpecError as ex:
                return f"REFUSED-AT-RUN {str(ex)[:40]} still={sys.getprofile() is p}"
    finally:
        sys.setprofile(None)
# R1-D1 non-LIFO / reentry
@case("R1-D1 two tracers exited non-LIFO, same target", "PASS")
def _():
    e1 = mkexp(G={"exercises": [f"{M}:f"]}); e2 = mkexp(G={"exercises": [f"{M}:f"]})
    orig = fx.f.__code__
    t1 = coverage_trace(e1).__enter__(); t2 = coverage_trace(e2).__enter__()
    t1.run("G", fx.f, 1); t2.run("G", fx.f, 1)
    t1.__exit__(None, None, None); t2.__exit__(None, None, None)
    r = score(e1, t1.record())
    return r if fx.f.__code__ is orig else "CODE NOT RESTORED"
@case("R1-D1 v: tracer entered twice, second swallowed -> REENTRY at score", "REFUSED [V5:REENTRY]")
def _():
    e = mkexp(G={"exercises": [f"{M}:f"]})
    with coverage_trace(e) as c:
        try: c.__enter__()
        except GateSpecError: pass
        c.run("G", fx.f, 1)
    return score(e, c.record())
# R1-D2 resolution crashes
_bd = Path(tempfile.mkdtemp()); (_bd / "ca_held_bad.py").write_text("raise RuntimeError('boom at import')\n"); sys.path.insert(0, str(_bd))
@case("R1-D2 module raising RuntimeError at import", "REFUSED-AT-ENTRY [V5:UNRESOLVED]")
def _(): return one(["ca_held_bad:f"], lambda c: None)
@case("R1-D2 v: __wrapped__ cycle of 2 functions, foreign globals (bounded walk)", "REFUSED-AT-ENTRY [V5:FOREIGN_DEFINITION]")
def _():
    a = lambda: 1; b = lambda: 2; a.__wrapped__ = b; b.__wrapped__ = a
    fx.cyc = a
    try: return one([f"{M}:cyc"], lambda c: None)
    finally: del fx.cyc
@case("R1-D2 v: 40-hop foreign __wrapped__ chain reaching module fn (16-hop cap)", "REFUSED-AT-ENTRY [V5:FOREIGN_DEFINITION]")
def _():
    cur = fx.f
    for _ in range(40):
        cur = functools.wraps(cur)(lambda *a: 0)
    fx.deep = cur
    try: return one([f"{M}:deep"], lambda c: None)
    finally: del fx.deep
# R1-D3 non-string trace keys
@case("R1-D3 int key in targets", "REFUSED [V5:BAD_TRACE]")
def _():
    e, rec = trace([f"{M}:f"], lambda c: c.run("G", fx.f, 1)); rec["targets"][1] = "x"; return score(e, rec)
@case("R1-D3 v: None key in sections", "REFUSED [V5:BAD_TRACE]")
def _():
    e, rec = trace([f"{M}:f"], lambda c: c.run("G", fx.f, 1)); rec["sections"][None] = rec["sections"]["G"]; return score(e, rec)
# R1-N2
@case("R1-N2 Sub.fit inherited", "REFUSED-AT-ENTRY [V5:INHERITED]")
def _(): return one([f"{M}:Sub.fit"], lambda c: c.run("G", fx.Other().fit))
# R2-B1
@case("R2-B1 runtime no-wraps decoration timed(cheap_path) for score_all", "REFUSED [V5:NOT_EXERCISED]")
def _(): return one([f"{M}:score_all"], lambda c: c.run("G", fx._timed(fx.cheap_path)))
# R2-B2 pool shared by concurrently open sections
@case("R2-B2 pool warmed by A; B's unsectioned job while both open (gate A)", "REFUSED [V5:NOT_EXERCISED]")
def _():
    def h(c):
        ex = cf.ThreadPoolExecutor(1)
        a_open, b_done = threading.Event(), threading.Event()
        def A():
            ex.submit(lambda: None).result(); a_open.set(); b_done.wait(5)
        def B():
            a_open.wait(5); ex.submit(fx.f, 1).result(); b_done.set()
        ta = threading.Thread(target=c.run, args=("A", A)); tb = threading.Thread(target=c.run, args=("B", B))
        ta.start(); tb.start(); ta.join(); tb.join(); ex.shutdown()
    e, rec = trace(None, h, {"A": [f"{M}:f"], "B": [f"{M}:g"]})
    return gate(e, rec, "A")
# R2-B3 thread hook persists
@case("R2-B3 worker's profiler after its section and tracer exit", "None")
def _():
    box = {}
    e = mkexp(G={"exercises": [f"{M}:f"]})
    with coverage_trace(e) as c:
        ev = threading.Event()
        def worker():
            c.run("G", fx.f, 1); ev.wait(5); fx.g(1); box["p"] = sys.getprofile()
        t = threading.Thread(target=worker); t.start()
    ev.set(); t.join()
    return str(box["p"])
# R2-D1 instance path
@case("R2-D1 default_model.fit via instance", "REFUSED-AT-ENTRY [V5:INSTANCE_PATH]")
def _(): return one([f"{M}:default_model.fit"], lambda c: c.run("G", fx.Other().fit))
# R2-D2 wraps siblings (same decorator code object)
@case("R2-D2 wraps siblings: declare run_fast, call run_safe", "REFUSED [V5:NOT_EXERCISED]")
def _(): return one([f"{M}:run_fast"], lambda c: c.run("G", fx.run_safe, 1))
@case("R3-D1a plain caller of the wraps inner (run_plain) for run_fast", "REFUSED [V5:NOT_EXERCISED]")
def _(): return one([f"{M}:run_fast"], lambda c: c.run("G", fx.run_plain, 1))
@case("R3-D1c per-call wraps sibling built in the section", "REFUSED [V5:NOT_EXERCISED]")
def _(): return one([f"{M}:run_fast"], lambda c: c.run("G", lambda: fx.deco_wraps(fx._run)(1)))
# R2-D4 RecursionError
@case("R2-D4 RecursionError in a traced recursion, caught after the target", "PASS")
def _():
    def sec():
        fx.f(1)
        try: fx.rec(0)
        except RecursionError: pass
    return one([f"{M}:f"], lambda c: c.run("G", sec))
# R3-B1
@case("R3-B1 make_mul(3)(5) for double", "REFUSED [V5:NOT_EXERCISED]")
def _(): return one([f"{M}:double"], lambda c: c.run("G", lambda: fx.make_mul(3)(5)))
# R3-B2 asyncio shared consumer
@case("R3-B2 A's lazily started consumer tasks run B's job (gate A)", "REFUSED [V5:NOT_EXERCISED]")
def _():
    def h(c):
        async def main():
            q = asyncio.Queue(); st = {}
            async def consumer():
                while True:
                    job = await q.get(); job(); q.task_done()
            async def A():
                st["t"] = asyncio.get_running_loop().create_task(consumer())
                await asyncio.sleep(0.02)
            async def B():
                q.put_nowait(lambda: fx.f(1)); await q.join()
            await asyncio.gather(c.run_async("A", A), c.run_async("B", B))
            st["t"].cancel()
        asyncio.run(main())
    e, rec = trace(None, h, {"A": [f"{M}:f"], "B": [f"{M}:g"]})
    return gate(e, rec, "A")
# R3-B3 signal exceptions propagate
@case("R3-B3 SIGALRM Timeout inside traced loop propagates 5/5", "5/5")
def _():
    class Timeout(Exception): pass
    def on(sig, frm): raise Timeout()
    old = signal.signal(signal.SIGALRM, on); n = 0
    try:
        for _ in range(5):
            def sec():
                fx.f(1)
                signal.setitimer(signal.ITIMER_REAL, 0.02)
                t0 = time.time()
                while time.time() - t0 < 2: fx.g(1)
            try:
                one([f"{M}:f"], lambda c: c.run("G", sec))
            except Timeout:
                n += 1
            signal.setitimer(signal.ITIMER_REAL, 0)
    finally:
        signal.signal(signal.SIGALRM, old)
    return f"{n}/5"
# R3-D2 swallowed open-time refusal
@case("R3-D2 swallowed NESTED_SECTION refuses at score", "REFUSED [V5:NESTED_SECTION]")
def _():
    def h(c):
        def A():
            fx.f(1)
            try: c.run("G", fx.f, 2)
            except GateSpecError: pass
        c.run("G", A)
    return one([f"{M}:f"], h)
# R3-D5 daemon thread outlives the section
@case("R3-D5 daemon thread started in section outlives it", "PASS")
def _():
    def sec():
        fx.f(1); threading.Thread(target=time.sleep, args=(0.3,), daemon=True).start()
    return one([f"{M}:f"], lambda c: c.run("G", sec))
# R3-D6 singledispatch, same name in two shards
@case("R3-D6 singledispatch dispatcher declared, dispatch(1)", "PASS")
def _(): return one([f"{M}:dispatch"], lambda c: c.run("G", fx.dispatch, 1))
@case("R3-D6 two threads shard section G concurrently", "PASS")
def _():
    def h(c):
        ts = [threading.Thread(target=c.run, args=("G", fx.f, i)) for i in range(2)]
        [t.start() for t in ts]; [t.join() for t in ts]
    return one([f"{M}:f"], h)
# J1-X1 stub before the trace
@case("J1-X1 stub from another module bound before the trace", "REFUSED-AT-ENTRY [V5:FOREIGN_DEFINITION]")
def _():
    real = fx.g; fx.g = vend.f
    try: return one([f"{M}:g"], lambda c: c.run("G", fx.g, 1))
    finally: fx.g = real
@case("J1-X1 v: unittest.mock.patch(autospec=True) before the trace", "REFUSED-AT-ENTRY [V5:FOREIGN_DEFINITION]")
def _():
    from unittest import mock
    with mock.patch(f"{M}.g", autospec=True):
        return one([f"{M}:g"], lambda c: c.run("G", fx.g, 1))
# counts: generator resumptions
@case("frame entries: two-yield generator consumed", "PASS verdict=PASS coverage={'G': {'ca_held:gen': 3}}")
def _(): return one([f"{M}:gen"], lambda c: c.run("G", lambda: list(fx.gen())))
print(f"{sum(rows)}/{len(rows)} held")
print("no finding: every rebuilt round-1..3 attack and variant in this battery held" if all(rows)
      else "FINDING-REPRODUCED: a rebuilt closure attack broke (see BROKE lines)")
