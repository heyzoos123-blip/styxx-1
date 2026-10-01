"""round4/exam-mutation/r1/m_*.py, rewritten: each file's paired HARNESS (the API program); their other half (the
v5e mutant run against v5e's frozen exam) is exam tooling for v5e (NOT_APPLICABLE.json). d_wraps_over_class_
wrapper_overblock.py is the same shape as verify/wraps-over-class-wrapper-overblock (r4_vf_identity, variant A).
gate(e, rec, name) is the per-gate view through check_metrics (the harnesses used the private _check_coverage).
B01 a str-subclass opening end; C01 a run_async B opened on a worker thread and finished inside section A; C02 and
C06 a profiler started mid-section; D01 a declared section 'sección'; E01 an in-place hot reload of the declared
function's __code__ in the section; E04 a nested shorter trace exits first, then A runs a loop serving another
thread's jobs; E05 an explicit exit then a cleanup exit, then a later trace; E07 a profiler started after the last
section; K01 two threads run section B whose loop dispatches g; O05 task A starts a profiler while B opens; O07
an inner trace of another prereg with the same gate name opened inside the outer's section; S01 a trace scored
against an edited prereg; S02 a recorded CLONE_CALLED plus a bad count."""
import asyncio, sys, threading


class S(str):
    pass


class _Yield:
    def __await__(self):
        yield


def main(api):
    out = {}

    def gate(e, rec, name):
        m = api.metrics(e, {"m": 1.0, "coverage_trace": rec})
        return m.get(name + ":exercises", m) if isinstance(m, dict) else m

    def trace_of(e, h):
        cov = api.coverage_trace(e)
        with cov:
            h(cov)
        return cov.record()
    m = api.fixture("rp_em_b01", "def f(): return 1\n")
    e = api.exp({"G": ["rp_em_b01:f"]})
    rec = trace_of(e, lambda c: c.run("G", m.f))
    rec["sections"]["G"][0]["end"] = S("returned")
    out["B01"] = gate(e, rec, "G")
    m = api.fixture("rp_em_c01", "def f(): return 1\ndef g(): return 2\n")
    e = api.exp({"A": ["rp_em_c01:f"], "B": ["rp_em_c01:g"]})

    def c01(cov):
        async def bjob():
            m.g()
            await _Yield()
        c = cov.run_async("B", bjob)
        t = threading.Thread(target=c.send, args=(None,))
        t.start()
        t.join()

        def abody():
            try:
                c.send(None)
            except StopIteration:
                pass
            m.f()
        cov.run("A", abody)
    rec = trace_of(e, c01)
    out["C01"] = {"A": gate(e, rec, "A"), "B": gate(e, rec, "B"), "record": api.norm(rec)}
    m = api.fixture("rp_em_c02", "def f(): return 1\ndef g(): return 2\n")
    e = api.exp({"G": ["rp_em_c02:f", "rp_em_c02:g"]})

    def my_profiler(frame, event, arg):
        return None

    def c02(cov):
        def body():
            m.f()
            sys.setprofile(my_profiler)
            m.g()
        try:
            cov.run("G", body)
        finally:
            sys.setprofile(None)
    rec = trace_of(e, c02)
    out["C02"] = {"gate": gate(e, rec, "G"), "notes": [api.text(n) for n in rec["sections"]["G"][0]["notes"]]}
    m = api.fixture("rp_em_c06", "def f(): return 1\n")
    e = api.exp({"G": ["rp_em_c06:f"]})
    seen, box = [], {}

    def prof2(frame, event, arg):
        seen.append(event)

    def c06(cov):
        def body():
            m.f()
            sys.setprofile(prof2)
        cov.run("G", body)
        box["still"] = sys.getprofile() is prof2
        sys.setprofile(None)
    rec = trace_of(e, c06)
    out["C06"] = {"still_installed_after_close": box.get("still"), "gate": gate(e, rec, "G")}
    api.fixture("rp_em_d01", "def f(): return 1\n")
    out["D01"] = api.attempt(lambda: api.exp({"G": ["rp_em_d01:f"]}, sections={"G": "sección"}) and "accepted")
    m = api.fixture("rp_em_e01", "def f():\n    return 'v1'\n")
    ns = {}
    exec(compile("def f():\n    return 'v2'\n", m.__file__, "exec"), ns)
    e = api.exp({"G": ["rp_em_e01:f"]})

    def e01(cov):
        def body():
            m.f()
            m.f.__code__ = ns["f"].__code__
        cov.run("G", body)
    rec = trace_of(e, e01)
    out["E01"] = {"after_exit": m.f(), "gate": gate(e, rec, "G")}
    m = api.fixture("rp_em_e04", "def f(): return 1\ndef g(): return 2\n")
    eo, ei = api.exp({"A": ["rp_em_e04:f"]}), api.exp({"H": ["rp_em_e04:g"]})

    def e04(cov):
        out["E04_inner"] = api.trace(ei, lambda c: c.run("H", m.g))

        def body():
            loop = asyncio.new_event_loop()
            ready = threading.Event()

            async def job():
                m.f()

            def foreign():
                ready.wait(5)
                asyncio.run_coroutine_threadsafe(job(), loop).result(5)
                loop.call_soon_threadsafe(m.f)
                loop.call_soon_threadsafe(loop.stop)
            t = threading.Thread(target=foreign)
            t.start()
            loop.call_soon(ready.set)
            loop.run_forever()
            t.join()
            loop.close()
        cov.run("A", body)
    rec = trace_of(eo, e04)
    out["E04"] = {"gate": gate(eo, rec, "A"), "calls": rec["sections"]["A"][0]["calls"], "uncredited": rec["uncredited"]}
    m = api.fixture("rp_em_e05", "def f(): return 1\n")
    e = api.exp({"G": ["rp_em_e05:f"]})
    cov = api.coverage_trace(e)
    r = {"enter": api.attempt(lambda: cov.__enter__() is cov)}
    try:
        cov.run("G", m.f)
        r["exit1"] = api.attempt(lambda: bool(cov.__exit__(None, None, None)))
    finally:
        r["exit2"] = api.attempt(lambda: bool(cov.__exit__(None, None, None)))
    r["first"] = gate(e, cov.record(), "G")
    e2 = api.exp({"H": ["rp_em_e05:f"]})
    r["second"] = gate(e2, trace_of(e2, lambda c: c.run("H", m.f)), "H")
    r["state"] = api.state()
    out["E05"] = r
    m = api.fixture("rp_em_e07", "def f(): return 1\n")
    e = api.exp({"G": ["rp_em_e07:f"]})
    cov = api.coverage_trace(e)
    with cov:
        cov.run("G", m.f)
        sys.setprofile(my_profiler)
    still = sys.getprofile() is my_profiler
    sys.setprofile(None)
    out["E07"] = {"still_installed_after_exit": still, "gate": gate(e, cov.record(), "G")}
    m = api.fixture("rp_em_k01", "def f(): return 1\ndef g(): return 2\n")
    e = api.exp({"A": ["rp_em_k01:g"], "B": ["rp_em_k01:f"]})

    def k01(cov):
        def shard():
            def body():
                m.f()
                loop = asyncio.new_event_loop()
                loop.call_soon(m.g)
                loop.call_soon(loop.stop)
                loop.run_forever()
                loop.close()
            cov.run("B", body)
        ts = [threading.Thread(target=shard) for _ in range(2)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        cov.run("A", lambda: None)
    out["K01"] = trace_of(e, k01)["uncredited"]
    m = api.fixture("rp_em_o05", "def f(): return 1\ndef g(): return 2\n")
    e = api.exp({"A": ["rp_em_o05:f"], "B": ["rp_em_o05:g"]})
    raised = []

    def o05(cov):
        async def a():
            m.f()
            sys.setprofile(my_profiler)
            await asyncio.sleep(0.01)
            sys.setprofile(None)

        async def b():
            await asyncio.sleep(0)
            m.g()

        async def amain():
            res = await asyncio.gather(cov.run_async("A", a), cov.run_async("B", b), return_exceptions=True)
            raised.extend(api.text(str(x)).get("code") for x in res if isinstance(x, BaseException))
        try:
            asyncio.run(amain())
        finally:
            sys.setprofile(None)
    rec = trace_of(e, o05)
    out["O05"] = {"raised_at_open": raised, "B": gate(e, rec, "B"), "problems": api.norm(rec)["problems"]}
    m = api.fixture("rp_em_o07", "def f(): return 1\n")
    es, et = api.exp({"G1": ["rp_em_o07:f"]}), api.exp({"G1": ["rp_em_o07:f"]})
    box = {}

    def o07(outer):
        def body():
            inner = api.coverage_trace(et)
            with inner:
                try:
                    inner.run("G1", m.f)
                except api.GateSpecError as ex:
                    box["raised"] = api.text(str(ex)).get("code")
            box["inner"] = inner.record()
        outer.run("G1", body)
    rec = trace_of(es, o07)
    out["O07"] = {"outer": gate(es, rec, "G1"), "inner": gate(et, box["inner"], "G1"), "raised": box.get("raised")}
    m = api.fixture("rp_em_s01", "def f(): return 1\ndef g(): return 2\n")
    old, new = api.exp({"G": ["rp_em_s01:f"]}), api.exp({"G": ["rp_em_s01:f", "rp_em_s01:g"]})
    out["S01"] = gate(new, trace_of(old, lambda c: c.run("G", lambda: (m.f(), m.g()) and None)), "G")
    m = api.fixture("rp_em_s02", "def f(): return 1\n")
    e = api.exp({"G": ["rp_em_s02:f"]})
    rec = trace_of(e, lambda c: c.run("G", lambda: (m.f(), exec(m.f.__code__, {})) and None))
    rec["sections"]["G"][0]["calls"]["rp_em_s02:f"] = 0
    out["S02"] = gate(e, rec, "G")
    return out
