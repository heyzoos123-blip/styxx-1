"""round4/closure-audit/r1/held_battery.py (the round 1-3 closure battery, 41 rows), re-targeted to v5f's public
API (G_CLOSURE). Each row runs the battery's scenario and reduces its outcome to a spec-fixed string:
  "PASS" / "PASS <coverage>"           score() returned PASS (the generator row adds its coverage);
  "REFUSED <CODE>"                     score() refused, or for a per-gate row, check_metrics' <gate>:exercises
                                       note (the battery's private e._check_coverage(name) re-targeted to the
                                       public per-gate view);
  "ENTRY <CODE>" / "RUN <CODE>"        coverage_trace()/__enter__ or cov.run refused;
  "ESCAPED <ExceptionType>"            anything else escaped;
  plus a row-specific value where the battery printed one (R2-B3's profiler, R3-B3's n/5).
Every row also checks the at-rest state the battery's clean() checked, through public observables: _v5_state()
has no anchors, no mints, the guard free and no global events, and sys.getprofile() and sys.gettrace() are None.
Re-targeting changes, row by row, are in RETARGETED; v5f's expected outcome per row, with where the text states
it, is in EXPECT. `closure(obs)` gives held/BROKE per row (G_CLOSURE holds iff 41/41 on each verified
interpreter)."""
import asyncio, concurrent.futures as cf, copy, functools, marshal, signal, sys, threading, time, types

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
M = "rp_ca_held"

# v5f's expected outcome per row. "battery" = the battery's own expectation carries over unchanged (the closure
# table, "Finding closure, rounds 1-3", keeps the row's class CLOSED with the same refusal); otherwise the text
# passage that sets the v5f outcome. Rows marked "derived" are the exam author's reading (Revision 13 follow-ups).
EXPECT = {
    "R1-B1 factory sibling": ("REFUSED NOT_EXERCISED", "battery"),
    "R1-B1 v sibling built during the trace": ("REFUSED NOT_EXERCISED", "battery"),
    "R1-B1 no-wraps decorator sibling": ("REFUSED NOT_EXERCISED", "battery"),
    "R1-B1 v declare both siblings call one": ("REFUSED NOT_EXERCISED", "battery"),
    "R1-B2 vendored equal copy": ("REFUSED NOT_EXERCISED", "battery"),
    "R1-B2 v marshal round-trip clone": ("REFUSED NOT_EXERCISED", "battery"),
    "R1-B2 dataclass DB for DA.__init__": ("REFUSED NOT_EXERCISED", "battery"),
    "R1-B2 v deepcopy(f) is f": ("PASS", "battery"),
    "R1-B3 thread from A calls f during B (gate B)": ("REFUSED NOT_EXERCISED", "battery"),
    "R1-B3 v asyncio task from A awaited in B (gate B)": ("REFUSED NOT_EXERCISED", "battery"),
    "R1-B3 v call_soon_threadsafe into a loop inside A": ("REFUSED NOT_EXERCISED", "battery"),
    "R1-B3 v pool job submitted from A": ("REFUSED NOT_EXERCISED", "battery"),
    "R1-B3 v Timer started in A": ("REFUSED NOT_EXERCISED", "battery"),
    "R1-B4 cProfile enabled before open": ("PASS", "battery on 3.12+ (the verified interpreters)"),
    "R1-B4 v pure-Python profiler present at open": (
        "PASS profiler_kept", "derived: R1-B4 row 'styxx never calls setprofile, so no profiler is ever called, "
        "chained, replaced or removed (V33, V48)'; 'profile-module-refuses-on-312': FOREIGN_PROFILER is retired, "
        "V48's shape is expected to coexist. The battery expected RUN FOREIGN_PROFILER (v5e)"),
    "R1-D1 non-LIFO exits same target": ("PASS", "battery"),
    "R1-D1 v entered twice second swallowed": ("REFUSED REENTRY", "battery"),
    "R1-D2 module raising at import": ("ENTRY UNRESOLVED", "battery"),
    "R1-D2 v __wrapped__ cycle foreign globals": ("ENTRY FOREIGN_DEFINITION", "battery"),
    "R1-D2 v 40-hop foreign __wrapped__ chain": ("ENTRY FOREIGN_DEFINITION", "battery"),
    "R1-D3 int key in an opening's calls": ("REFUSED BAD_TRACE", "derived: v5f's record has no 'targets' (the battery's int key in targets); R1-D3 row: the exact type is tested before every hash or compare (X96-X108)"),
    "R1-D3 v None key in sections": ("REFUSED BAD_TRACE", "battery"),
    "R1-N2 Sub.fit inherited": ("ENTRY INHERITED", "battery"),
    "R2-B1 runtime no-wraps decoration": ("REFUSED NOT_EXERCISED", "battery"),
    "R2-B2 pool warmed by A runs B's job (gate A)": ("REFUSED NOT_EXERCISED", "battery"),
    "R2-B3 worker's profiler after exit": ("None", "battery"),
    "R2-D1 instance path": ("ENTRY INSTANCE_PATH", "battery"),
    "R2-D2 wraps siblings": ("REFUSED NOT_EXERCISED", "battery"),
    "R3-D1a plain caller of the wraps inner": ("REFUSED NOT_EXERCISED", "battery"),
    "R3-D1c per-call wraps sibling": ("REFUSED NOT_EXERCISED", "battery"),
    "R2-D4 RecursionError caught after the target": ("PASS", "battery"),
    "R3-B1 make_mul(3) for double": ("REFUSED NOT_EXERCISED", "battery"),
    "R3-B2 A's consumer tasks run B's job (gate A)": ("REFUSED NOT_EXERCISED", "battery"),
    "R3-B3 SIGALRM Timeout propagates": ("5/5", "battery"),
    "R3-D2 swallowed NESTED_SECTION": ("REFUSED NESTED_SECTION", "battery"),
    "R3-D5 daemon thread outlives the section": ("PASS", "battery"),
    "R3-D6 singledispatch dispatcher": ("PASS", "battery"),
    "R3-D6 two threads shard G": ("PASS", "battery"),
    "J1-X1 stub from another module": ("ENTRY FOREIGN_DEFINITION", "battery"),
    "J1-X1 v mock.patch autospec": ("ENTRY FOREIGN_DEFINITION", "battery"),
    "frame entries two-yield generator": ("PASS {'G': {'rp_ca_held:gen': 3}}", "battery"),
}
RETARGETED = {
    "all": "the battery's clean() read v5e's private registries (_MINTED, _BY_FN, _ANCHORS, _THREADS, _ACTIVE); "
           "here _v5_state() (anchors, mints, guard, global_events) and sys.getprofile()/gettrace()",
    "per-gate rows": "the battery's e._check_coverage(name) (private) is check_metrics(result)[name + ':exercises']",
    "R1-D3 int key in an opening's calls": "v5f's record has no 'targets' mapping; the int key goes into an opening's calls",
    "fixture modules": "rp_ca_held / rp_ca_held_vendored / rp_ca_held_bad (the battery's ca_held*)",
}


def _code(msg):
    return msg[4:msg.index("]")] if msg.startswith("[V5:") and "]" in msg else "?"


def main(api):
    P = api.P
    GSE = api.GateSpecError
    fx = api.fixture(M, SRC)
    vend = api.fixture("rp_ca_held_vendored", "def f(x=0): return x\n")
    api.write("rp_ca_held_bad", "raise RuntimeError('boom at import')\n")
    rows = {}

    def clean():
        st = P._v5_state()
        return (st.get("anchors") == 0 and st.get("mints") == [] and st.get("guard") == "free"
                and st.get("global_events") == 0 and sys.getprofile() is None and sys.gettrace() is None)

    def case(row):
        def deco(fn):
            try:
                got = fn()
            except GSE as ex:
                got = "ENTRY " + _code(str(ex))
            except BaseException as ex:                # noqa: BLE001
                got = "ESCAPED " + type(ex).__name__
            rows[row] = {"outcome": got, "clean": clean()}
            sys.setprofile(None)
            return fn
        return deco

    def score(e, rec):
        try:
            v = e.score({"m": 1.0, "coverage_trace": rec})
            return "PASS" if v.verdict == "PASS" else "VERDICT " + str(v.verdict)
        except GSE as ex:
            return "REFUSED " + _code(str(ex))

    def mk(sections):
        return api.exp({s: t for s, t in sections.items()}, sections={s: s for s in sections})

    def trace(sections, harness):
        e = mk(sections)
        with api.coverage_trace(e) as cov:
            harness(cov)
        return e, cov.record()

    def gate(e, rec, name):
        try:
            n = e.check_metrics({"m": 1.0, "coverage_trace": rec}).get(name + ":exercises", {})
        except BaseException as ex:                    # noqa: BLE001
            return "ESCAPED " + type(ex).__name__
        if n.get("usable"):
            return "PASS"
        note = n.get("note")
        return "REFUSED " + (_code(note) if isinstance(note, str) else str(note))

    def one(targets, harness):
        return score(*trace({"G": targets}, harness))

    @case("R1-B1 factory sibling")
    def _(): return one([f"{M}:check_low"], lambda c: c.run("G", fx.check_high, 5))

    @case("R1-B1 v sibling built during the trace")
    def _(): return one([f"{M}:check_low"], lambda c: c.run("G", lambda: fx._make(1)(5)))

    @case("R1-B1 no-wraps decorator sibling")
    def _(): return one([f"{M}:entry_a"], lambda c: c.run("G", fx.entry_b))

    @case("R1-B1 v declare both siblings call one")
    def _(): return one([f"{M}:check_low", f"{M}:check_high"], lambda c: c.run("G", fx.check_low, 1))

    @case("R1-B2 vendored equal copy")
    def _(): return one([f"{M}:f"], lambda c: c.run("G", vend.f, 1))

    @case("R1-B2 v marshal round-trip clone")
    def _(): return one([f"{M}:f"], lambda c: c.run("G", lambda: types.FunctionType(
        marshal.loads(marshal.dumps(fx.f.__code__)), fx.f.__globals__)(1)))

    @case("R1-B2 dataclass DB for DA.__init__")
    def _(): return one([f"{M}:DA.__init__"], lambda c: c.run("G", fx.DB))

    @case("R1-B2 v deepcopy(f) is f")
    def _(): return one([f"{M}:f"], lambda c: c.run("G", copy.deepcopy(fx.f), 1))

    def thread_in_A_calls_during_B(c):
        go, done = threading.Event(), threading.Event()

        def worker():
            go.wait(5)
            fx.f(1)
            done.set()
        c.run("A", lambda: threading.Thread(target=worker).start())

        def B():
            go.set()
            done.wait(5)
        c.run("B", B)

    @case("R1-B3 thread from A calls f during B (gate B)")
    def _():
        e, rec = trace({"A": [f"{M}:g"], "B": [f"{M}:f"]}, thread_in_A_calls_during_B)
        return gate(e, rec, "B")

    @case("R1-B3 v asyncio task from A awaited in B (gate B)")
    def _():
        def h(c):
            box = {}

            async def A():
                async def job():
                    fx.f(1)
                box["t"] = asyncio.get_running_loop().create_task(job())

            async def B():
                await box["t"]

            async def drive():
                await c.run_async("A", A)
                await c.run_async("B", B)
            asyncio.run(drive())
        e, rec = trace({"A": [f"{M}:g"], "B": [f"{M}:f"]}, h)
        return gate(e, rec, "B")

    @case("R1-B3 v call_soon_threadsafe into a loop inside A")
    def _():
        def h(c):
            def A():
                loop = asyncio.new_event_loop()

                def other():
                    loop.call_soon_threadsafe(fx.f, 1)
                    loop.call_soon_threadsafe(loop.stop)
                threading.Thread(target=other).start()
                loop.run_forever()
                loop.close()
            c.run("A", A)
        return score(*trace({"A": [f"{M}:f"]}, h))

    @case("R1-B3 v pool job submitted from A")
    def _():
        def h(c):
            with cf.ThreadPoolExecutor(2) as ex:
                c.run("A", lambda: ex.submit(fx.f, 1).result())
        return score(*trace({"A": [f"{M}:f"]}, h))

    @case("R1-B3 v Timer started in A")
    def _():
        def h(c):
            def A():
                t = threading.Timer(0.01, fx.f, (1,))
                t.start()
                t.join()
            c.run("A", A)
        return score(*trace({"A": [f"{M}:f"]}, h))

    @case("R1-B4 cProfile enabled before open")
    def _():
        import cProfile
        pr = cProfile.Profile()
        pr.enable()
        try:
            e = mk({"G": [f"{M}:f"]})
            with api.coverage_trace(e) as c:
                try:
                    c.run("G", fx.f, 1)
                except GSE as ex:
                    return "RUN " + _code(str(ex))
            return score(e, c.record())
        finally:
            pr.disable()

    @case("R1-B4 v pure-Python profiler present at open")
    def _():
        p = lambda fr, ev, a: None                     # noqa: E731
        sys.setprofile(p)
        try:
            e = mk({"G": [f"{M}:f"]})
            with api.coverage_trace(e) as c:
                try:
                    c.run("G", fx.f, 1)
                except GSE as ex:
                    return "RUN " + _code(str(ex))
                kept = sys.getprofile() is p
            return score(e, c.record()) + (" profiler_kept" if kept else " profiler_lost")
        finally:
            sys.setprofile(None)

    @case("R1-D1 non-LIFO exits same target")
    def _():
        e1, e2 = mk({"G": [f"{M}:f"]}), mk({"G": [f"{M}:f"]})
        orig = fx.f.__code__
        t1 = api.coverage_trace(e1).__enter__()
        t2 = api.coverage_trace(e2).__enter__()
        t1.run("G", fx.f, 1)
        t2.run("G", fx.f, 1)
        t1.__exit__(None, None, None)
        t2.__exit__(None, None, None)
        r = score(e1, t1.record())
        return r if fx.f.__code__ is orig else "CODE NOT RESTORED"

    @case("R1-D1 v entered twice second swallowed")
    def _():
        e = mk({"G": [f"{M}:f"]})
        with api.coverage_trace(e) as c:
            try:
                c.__enter__()
            except GSE:
                pass
            c.run("G", fx.f, 1)
        return score(e, c.record())

    @case("R1-D2 module raising at import")
    def _(): return one(["rp_ca_held_bad:f"], lambda c: None)

    @case("R1-D2 v __wrapped__ cycle foreign globals")
    def _():
        a = lambda: 1                                  # noqa: E731
        b = lambda: 2                                  # noqa: E731
        a.__wrapped__ = b
        b.__wrapped__ = a
        fx.cyc = a
        try:
            return one([f"{M}:cyc"], lambda c: None)
        finally:
            del fx.cyc

    @case("R1-D2 v 40-hop foreign __wrapped__ chain")
    def _():
        cur = fx.f
        for _ in range(40):
            cur = functools.wraps(cur)(lambda *a: 0)
        fx.deep = cur
        try:
            return one([f"{M}:deep"], lambda c: None)
        finally:
            del fx.deep

    @case("R1-D3 int key in an opening's calls")
    def _():
        e, rec = trace({"G": [f"{M}:f"]}, lambda c: c.run("G", fx.f, 1))
        rec["sections"]["G"][0]["calls"][1] = 1
        return score(e, rec)

    @case("R1-D3 v None key in sections")
    def _():
        e, rec = trace({"G": [f"{M}:f"]}, lambda c: c.run("G", fx.f, 1))
        rec["sections"][None] = rec["sections"]["G"]
        return score(e, rec)

    @case("R1-N2 Sub.fit inherited")
    def _(): return one([f"{M}:Sub.fit"], lambda c: c.run("G", fx.Other().fit))

    @case("R2-B1 runtime no-wraps decoration")
    def _(): return one([f"{M}:score_all"], lambda c: c.run("G", fx._timed(fx.cheap_path)))

    @case("R2-B2 pool warmed by A runs B's job (gate A)")
    def _():
        def h(c):
            ex = cf.ThreadPoolExecutor(1)
            a_open, b_done = threading.Event(), threading.Event()

            def A():
                ex.submit(lambda: None).result()
                a_open.set()
                b_done.wait(5)

            def B():
                a_open.wait(5)
                ex.submit(fx.f, 1).result()
                b_done.set()
            ta = threading.Thread(target=c.run, args=("A", A))
            tb = threading.Thread(target=c.run, args=("B", B))
            ta.start()
            tb.start()
            ta.join()
            tb.join()
            ex.shutdown()
        e, rec = trace({"A": [f"{M}:f"], "B": [f"{M}:g"]}, h)
        return gate(e, rec, "A")

    @case("R2-B3 worker's profiler after exit")
    def _():
        box = {}
        e = mk({"G": [f"{M}:f"]})
        with api.coverage_trace(e) as c:
            ev = threading.Event()

            def worker():
                c.run("G", fx.f, 1)
                ev.wait(5)
                fx.g(1)
                box["p"] = sys.getprofile()
            t = threading.Thread(target=worker)
            t.start()
        ev.set()
        t.join()
        return str(box["p"])

    @case("R2-D1 instance path")
    def _(): return one([f"{M}:default_model.fit"], lambda c: c.run("G", fx.Other().fit))

    @case("R2-D2 wraps siblings")
    def _(): return one([f"{M}:run_fast"], lambda c: c.run("G", fx.run_safe, 1))

    @case("R3-D1a plain caller of the wraps inner")
    def _(): return one([f"{M}:run_fast"], lambda c: c.run("G", fx.run_plain, 1))

    @case("R3-D1c per-call wraps sibling")
    def _(): return one([f"{M}:run_fast"], lambda c: c.run("G", lambda: fx.deco_wraps(fx._run)(1)))

    @case("R2-D4 RecursionError caught after the target")
    def _():
        def sec():
            fx.f(1)
            try:
                fx.rec(0)
            except RecursionError:
                pass
        return one([f"{M}:f"], lambda c: c.run("G", sec))

    @case("R3-B1 make_mul(3) for double")
    def _(): return one([f"{M}:double"], lambda c: c.run("G", lambda: fx.make_mul(3)(5)))

    @case("R3-B2 A's consumer tasks run B's job (gate A)")
    def _():
        def h(c):
            async def drive():
                q, st = asyncio.Queue(), {}

                async def consumer():
                    while True:
                        job = await q.get()
                        job()
                        q.task_done()

                async def A():
                    st["t"] = asyncio.get_running_loop().create_task(consumer())
                    await asyncio.sleep(0.02)

                async def B():
                    q.put_nowait(lambda: fx.f(1))
                    await q.join()
                await asyncio.gather(c.run_async("A", A), c.run_async("B", B))
                st["t"].cancel()
            asyncio.run(drive())
        e, rec = trace({"A": [f"{M}:f"], "B": [f"{M}:g"]}, h)
        return gate(e, rec, "A")

    @case("R3-B3 SIGALRM Timeout propagates")
    def _():
        class Timeout(Exception):
            pass

        def on(sig, frm):
            raise Timeout()
        old = signal.signal(signal.SIGALRM, on)
        n = 0
        try:
            for _ in range(5):
                def sec():
                    fx.f(1)
                    signal.setitimer(signal.ITIMER_REAL, 0.02)
                    t0 = time.time()
                    while time.time() - t0 < 2:
                        fx.g(1)
                try:
                    one([f"{M}:f"], lambda c: c.run("G", sec))
                except Timeout:
                    n += 1
                signal.setitimer(signal.ITIMER_REAL, 0)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
        return f"{n}/5"

    @case("R3-D2 swallowed NESTED_SECTION")
    def _():
        def h(c):
            def A():
                fx.f(1)
                try:
                    c.run("G", fx.f, 2)
                except GSE:
                    pass
            c.run("G", A)
        return one([f"{M}:f"], h)

    @case("R3-D5 daemon thread outlives the section")
    def _():
        def sec():
            fx.f(1)
            threading.Thread(target=time.sleep, args=(0.3,), daemon=True).start()
        return one([f"{M}:f"], lambda c: c.run("G", sec))

    @case("R3-D6 singledispatch dispatcher")
    def _(): return one([f"{M}:dispatch"], lambda c: c.run("G", fx.dispatch, 1))

    @case("R3-D6 two threads shard G")
    def _():
        def h(c):
            ts = [threading.Thread(target=c.run, args=("G", fx.f, i)) for i in range(2)]
            [t.start() for t in ts]
            [t.join() for t in ts]
        return one([f"{M}:f"], h)

    @case("J1-X1 stub from another module")
    def _():
        real = fx.g
        fx.g = vend.f
        try:
            return one([f"{M}:g"], lambda c: c.run("G", fx.g, 1))
        finally:
            fx.g = real

    @case("J1-X1 v mock.patch autospec")
    def _():
        from unittest import mock
        with mock.patch(f"{M}.g", autospec=True):
            return one([f"{M}:g"], lambda c: c.run("G", fx.g, 1))

    @case("frame entries two-yield generator")
    def _():
        e, rec = trace({"G": [f"{M}:gen"]}, lambda c: c.run("G", lambda: list(fx.gen())))
        try:
            v = e.score({"m": 1.0, "coverage_trace": rec})
            return f"{v.verdict} {v.coverage}"
        except GSE as ex:
            return "REFUSED " + _code(str(ex))
    return rows


def closure(obs):
    """obs: main()'s rows. Returns {row: 'held' | 'BROKE ...'} and the count held."""
    out = {}
    for row, (want, _src) in EXPECT.items():
        got = (obs or {}).get(row)
        if got is None:
            out[row] = "BROKE (row missing)"
        elif got["outcome"] == want and got["clean"]:
            out[row] = "held"
        else:
            out[row] = f"BROKE got {got['outcome']!r} clean={got['clean']}"
    return out, sum(v == "held" for v in out.values())
