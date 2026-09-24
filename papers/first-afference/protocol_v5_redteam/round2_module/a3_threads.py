from rtlib import *
import fx_simple as fs, threading, time, asyncio, sys, _thread, contextvars
from concurrent.futures import ThreadPoolExecutor
E2 = lambda: exp(spec(A={"exercises": ["fx_simple:f"]}, B={"exercises": ["fx_simple:g"]}))

def run_in_executor_ok():
    # correct harness: section awaits its executor job; default executor lives on
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    with coverage_trace(e) as cov:
        async def main():
            with cov.section("G"):
                await asyncio.get_running_loop().run_in_executor(None, fs.f)
        asyncio.run(main())
    return score(e, cov.record())
attempt("A3a run_in_executor awaited inside section (correct)", run_in_executor_ok)

def to_thread_ok():
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    with coverage_trace(e) as cov:
        async def main():
            with cov.section("G"):
                await asyncio.to_thread(fs.f)
        asyncio.run(main())
    return score(e, cov.record())
attempt("A3b asyncio.to_thread awaited inside section (correct)", to_thread_ok)

def pool_outside():
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    with coverage_trace(e) as cov:
        with ThreadPoolExecutor(2) as pool:
            pool.submit(lambda: None).result()      # warmed outside any section
            with cov.section("G"):
                pool.submit(fs.f).result()
    r = cov.record(); return score(e, r) + f" unsectioned={r['unsectioned']}"
attempt("A3c pool created+warmed outside section, used inside (correct)", pool_outside)

def pool_first_used_in_A_then_B():
    e = E2()
    with coverage_trace(e) as cov:
        with ThreadPoolExecutor(1) as pool:
            with cov.section("A"): pool.submit(fs.f).result()
            with cov.section("B"): pool.submit(fs.g).result()
    return score(e, cov.record())
attempt("A3d pool shared by sequential sections (correct)", pool_first_used_in_A_then_B)

def concurrent_sections_shared_pool():
    # gates A and B run in parallel runner threads (started outside sections), sharing one pool
    # B's work (calls f) is executed by a worker the pool spawned while A was submitting.
    e = exp(spec(A={"exercises": ["fx_simple:f"]}, B={"exercises": ["fx_simple:g"]}))
    errs = []
    with coverage_trace(e) as cov:
        pool = ThreadPoolExecutor(1)
        a_started = threading.Event(); b_done = threading.Event(); pool_down = threading.Event()
        def gate_a():
            try:
                with cov.section("A"):
                    pool.submit(fs.g).result()     # A's own work: g only (NOT f)
                    a_started.set(); pool_down.wait()
            except Exception as ex: errs.append(repr(ex)[:120])
        def gate_b():
            try:
                a_started.wait()
                with cov.section("B"):
                    pool.submit(fs.g).result(); pool.submit(fs.f).result()
            except Exception as ex: errs.append(repr(ex)[:120])
            b_done.set()
        ta, tb = threading.Thread(target=gate_a), threading.Thread(target=gate_b)
        ta.start(); tb.start(); b_done.wait(); pool.shutdown(wait=True); pool_down.set()
        ta.join(); tb.join()
    r = cov.record()
    return f"errs={errs} sections={r['sections']} | " + score(e, r)
attempt("A3e concurrent sections sharing a pool", concurrent_sections_shared_pool)

def double_start():
    e = E2(); errs = []
    with coverage_trace(e) as cov:
        go = threading.Event()
        def w(): go.wait(); fs.g()
        t = threading.Thread(target=w)
        with cov.section("B"):
            fs.g(); t.start()
        # (B's close raises OUTLIVES -- skip) 
    return "n/a"
# skip

def thread_starts_thread_after_close():
    e = E2()
    with coverage_trace(e) as cov:
        inner = []
        rel = threading.Event()
        def outer():
            rel.wait()
            t2 = threading.Thread(target=fs.g); inner.append(t2); t2.start(); t2.join()
        with cov.section("A"):
            fs.f(); t1 = threading.Thread(target=outer); t1.start()
            rel.set(); t1.join()
    return score(e, cov.record())
attempt("A3f thread started in A starts a thread (joined) (control)", thread_starts_thread_after_close)

def start_new_thread():
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            done = threading.Event()
            _thread.start_new_thread(lambda: (fs.f(), done.set()), ()); done.wait()
    return score(e, cov.record())
attempt("A3g _thread.start_new_thread (stated limit, expect refusal)", start_new_thread)

def subclass_start_no_super():
    class T(threading.Thread):
        def start(self):
            import _thread as th
            self._started_manual = True
            threading.Thread.start(self)       # explicit base call, not super()
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            t = T(target=fs.f); t.start(); t.join()
    return score(e, cov.record())
attempt("A3h Thread subclass overriding start", subclass_start_no_super)

def timer():
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            t = threading.Timer(0.01, fs.f); t.start(); t.join()
    return score(e, cov.record())
attempt("A3i threading.Timer", timer)

def call_soon_ctx():
    e = E2()
    with coverage_trace(e) as cov:
        async def main():
            loop = asyncio.get_running_loop(); fut = loop.create_future()
            with cov.section("A"):
                fs.f(); loop.call_later(0.05, lambda: (fs.g(), fut.set_result(1)))
            with cov.section("B"):
                await fut
        asyncio.run(main())
    return score(e, cov.record())
attempt("A3j call_later scheduled in A fires in B (expect B refused)", call_soon_ctx)

def gen_resumed():
    e = E2()
    with coverage_trace(e) as cov:
        with cov.section("A"):
            fs.f(); it = fs.gen()
        with cov.section("B"):
            next(it)
    return score(e, cov.record())
attempt("A3k generator created in A, resumed in B (B executed it: expect PASS)", gen_resumed)

def copy_ctx():
    e = E2()
    with coverage_trace(e) as cov:
        with cov.section("A"):
            fs.f(); ctx = contextvars.copy_context()
        with cov.section("B"):
            ctx.run(fs.g)
    return score(e, cov.record())
attempt("A3l context copied in A, run in B (expect B refused)", copy_ctx)
