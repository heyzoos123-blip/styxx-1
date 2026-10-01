"""round2_module/a3_threads.py, rewritten (each part as the repro states it; waits are bounded):
a run_in_executor and b asyncio.to_thread awaited inside an async section; c a pool warmed outside, used inside;
d one pool shared by sequential sections; e concurrent sections in two runner threads sharing one pool (A submits
g only, B submits g and f); f a thread started in A starts and joins a thread; g _thread.start_new_thread in the
section; h a Thread subclass overriding start; i threading.Timer; j call_later scheduled in A fires during B;
k a generator created in A resumed in B; l a context copied in A run in B. (The repro's double_start was
skipped by the repro itself.)"""
import _thread, asyncio, contextvars, os, sys, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
from r2m_fx import SIMPLE


def main(api):
    fs = api.fixture("rp_fx_simple", SIMPLE)
    E1 = lambda: api.exp({"G": ["rp_fx_simple:f"]})
    E2 = lambda: api.exp({"A": ["rp_fx_simple:f"], "B": ["rp_fx_simple:g"]}, sections={"A": "A", "B": "B"})
    out = {}

    async def ex_body():
        return await asyncio.get_running_loop().run_in_executor(None, fs.f)
    out["a_run_in_executor"] = api.trace(E1(), lambda c: asyncio.run(c.run_async("G", ex_body)))

    async def tt_body():
        return await asyncio.to_thread(fs.f)
    out["b_to_thread"] = api.trace(E1(), lambda c: asyncio.run(c.run_async("G", tt_body)))
    pool = ThreadPoolExecutor(2)

    def warm(c):
        pool.submit(lambda: None).result()
    out["c_pool_warmed_outside"] = api.trace(E1(), warm, lambda c: c.run("G", lambda: pool.submit(fs.f).result()))
    pool.shutdown(wait=True)
    pool = ThreadPoolExecutor(1)
    out["d_pool_sequential"] = api.trace(E2(), lambda c: c.run("A", lambda: pool.submit(fs.f).result()),
                                         lambda c: c.run("B", lambda: pool.submit(fs.g).result()))
    pool.shutdown(wait=True)
    errs = []

    def concurrent(c):
        pool = ThreadPoolExecutor(1)
        a_started, b_done, pool_down = threading.Event(), threading.Event(), threading.Event()

        def gate_a():
            try:
                c.run("A", lambda: (pool.submit(fs.g).result(), a_started.set(), pool_down.wait(10)))
            except BaseException as ex:                # noqa: BLE001
                errs.append(type(ex).__name__)

        def gate_b():
            try:
                a_started.wait(10)
                c.run("B", lambda: (pool.submit(fs.g).result(), pool.submit(fs.f).result()))
            except BaseException as ex:                # noqa: BLE001
                errs.append(type(ex).__name__)
            b_done.set()
        ta, tb = threading.Thread(target=gate_a), threading.Thread(target=gate_b)
        ta.start()
        tb.start()
        b_done.wait(10)
        pool.shutdown(wait=True)
        pool_down.set()
        ta.join(10)
        tb.join(10)
    out["e_concurrent_shared_pool"] = api.trace(api.exp({"A": ["rp_fx_simple:f"], "B": ["rp_fx_simple:g"]},
                                                        sections={"A": "A", "B": "B"}), concurrent)
    out["e_errors"] = sorted(errs)

    def nested_threads():
        rel = threading.Event()

        def outer():
            rel.wait(10)
            t2 = threading.Thread(target=fs.g)
            t2.start()
            t2.join()
        fs.f()
        t1 = threading.Thread(target=outer)
        t1.start()
        rel.set()
        t1.join()
    out["f_thread_starts_thread"] = api.trace(E2(), lambda c: c.run("A", nested_threads))

    def snt():
        done = threading.Event()
        _thread.start_new_thread(lambda: (fs.f(), done.set()), ())
        done.wait(10)
    out["g_start_new_thread"] = api.trace(E1(), lambda c: c.run("G", snt))

    class T(threading.Thread):
        def start(self):
            self._started_manual = True
            threading.Thread.start(self)

    def sub():
        t = T(target=fs.f)
        t.start()
        t.join()
    out["h_thread_subclass_start"] = api.trace(E1(), lambda c: c.run("G", sub))

    def timer():
        t = threading.Timer(0.01, fs.f)
        t.start()
        t.join()
    out["i_timer"] = api.trace(E1(), lambda c: c.run("G", timer))

    def call_later(c):
        async def drive():
            loop = asyncio.get_running_loop()
            fut = loop.create_future()

            async def a():
                fs.f()
                loop.call_later(0.05, lambda: (fs.g(), fut.set_result(1)))

            async def b():
                await fut
            await c.run_async("A", a)
            await c.run_async("B", b)
        asyncio.run(drive())
    out["j_call_later_A_fires_in_B"] = api.trace(E2(), call_later)
    box = {}

    def ka():
        fs.f()
        box["it"] = fs.gen()
    out["k_generator_A_resumed_B"] = api.trace(E2(), lambda c: c.run("A", ka), lambda c: c.run("B", lambda: next(box["it"])))

    def la():
        fs.f()
        box["ctx"] = contextvars.copy_context()
    out["l_context_copied_A_run_B"] = api.trace(E2(), lambda c: c.run("A", la), lambda c: c.run("B", lambda: box["ctx"].run(fs.g)))
    return out
