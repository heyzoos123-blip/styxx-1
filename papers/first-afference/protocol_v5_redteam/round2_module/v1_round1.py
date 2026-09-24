from rtlib import *
import fx_factory as fx, fx_dc, fx_simple as fs, threading, time, sys
from concurrent.futures import ThreadPoolExecutor
def b1a():
    e = exp(spec(G={"exercises": ["fx_factory:check_high"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"): fx.check_low(0.5)
    return score(e, cov.record())
attempt("B1 factory closure", b1a)
def b1b():
    e = exp(spec(G={"exercises": ["fx_factory:entry_b"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"): fx.entry_a()
    return score(e, cov.record())
attempt("B1 no-wraps decorator", b1b)
def b2dc():
    e = exp(spec(G={"exercises": ["fx_dc:NullModel.__init__"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"): fx_dc.AltModel(3)
    return score(e, cov.record())
attempt("B2 dataclass __init__", b2dc)
def n2():
    e = exp(spec(G={"exercises": ["fx_dc:Sub.fit"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"): fx_dc.Other().fit()
    return score(e, cov.record())
attempt("N2 inherited Sub.fit", n2)
def b3a():
    e = exp(spec(A={"exercises": ["fx_simple:f"]}, B={"exercises": ["fx_simple:g"]}))
    with coverage_trace(e) as cov:
        with cov.section("A"):
            fs.f(); ex = ThreadPoolExecutor(1); ex.submit(fs.slow_then_g, 0.2); ex.shutdown(wait=False)
        with cov.section("B"): time.sleep(0.5)
        ex.shutdown(wait=True)
    return score(e, cov.record())
attempt("B3 thread outlives A (orig)", b3a)
def b3a2():
    # same, but harness catches OUTLIVES? no -- variant: A exits via exception (no alive check)
    e = exp(spec(A={"exercises": ["fx_simple:f"]}, B={"exercises": ["fx_simple:g"]}))
    with coverage_trace(e) as cov:
        try:
            with cov.section("A"):
                fs.f(); ex = ThreadPoolExecutor(1); ex.submit(fs.slow_then_g, 0.2); ex.shutdown(wait=False)
                raise ValueError("expected refusal")
        except ValueError: pass
        with cov.section("B"): time.sleep(0.5)
        ex.shutdown(wait=True)
    r = cov.record(); return score(e, r) + f" | after_close={r['after_close']}"
attempt("B3 variant: A exits by exception", b3a2)
def b3b():
    e = exp(spec(B={"exercises": ["fx_simple:g"]}))
    with coverage_trace(e) as cov:
        t = threading.Thread(target=fs.slow_then_g, args=(0.1,)); t.start()
        with cov.section("B"): time.sleep(0.3)
        t.join()
    return score(e, cov.record())
attempt("B3 thread started outside sections", b3b)
def b3c():
    import asyncio
    e = exp(spec(B={"exercises": ["fx_simple:f"]}, A={"exercises": ["fx_simple:g"]}))
    with coverage_trace(e) as cov:
        async def main():
            with cov.section("A"):
                fs.g(); t = asyncio.ensure_future(fs.af())
            with cov.section("B"):
                await t
        asyncio.run(main())
    return score(e, cov.record())
attempt("B3 asyncio task A->B", b3c)
def d1a():
    e = exp(spec(G={"exercises": ["fx_simple:f"]})); e2 = exp(spec(H={"exercises": ["fx_simple:g"]}))
    t1, t2 = coverage_trace(e), coverage_trace(e2)
    t1.__enter__(); t2.__enter__()
    try: t1.__exit__(None, None, None)
    except GateSpecError as ex: print("   t1 exit:", str(ex)[:60])
    t2.__exit__(None, None, None)
    return f"sys={sys.getprofile()} thr={threading.getprofile()}"
attempt("D1 non-LIFO", d1a)
def d1b():
    e = exp(spec(G={"exercises": ["fx_simple:f"]})); cov = coverage_trace(e)
    with cov:
        with cov: pass
attempt("D1 re-entry", d1b)
def d1d():
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    ev = threading.Event(); go = threading.Event(); seen = {}
    def worker():
        go.wait(); fs.f(); seen['p'] = sys.getprofile(); ev.set()
    with coverage_trace(e) as cov:
        th = threading.Thread(target=worker); th.start()
    go.set(); ev.wait(); th.join()
    return f"post-exit counted={cov.record()['unsectioned']} worker profile after exit={seen['p']}"
attempt("D1(d) thread keeps hook", d1d)
