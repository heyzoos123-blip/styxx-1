"""round3_module/t12_asyncio_shared_worker.py, rewritten: a lazily created pool of consumer tasks started by
whichever section first needs it (section A); gates A and B run concurrently as two run_async sections; A submits
g and then waits; B's pooled job, run by A-created workers while both are open, calls f; B calls g directly.
The repro's sleeps order A's first submit before B's (kept: B waits on an event A sets, then A waits for B)."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r3m_fx import SIMPLE


class Pool:
    def __init__(self):
        self.q, self.workers = None, []

    async def submit(self, fn):
        if self.q is None:
            self.q = asyncio.Queue()
            self.workers = [asyncio.create_task(self._work()) for _ in range(2)]
        fut = asyncio.get_running_loop().create_future()
        await self.q.put((fn, fut))
        return await fut

    async def _work(self):
        while True:
            fn, fut = await self.q.get()
            fut.set_result(fn())

    async def close(self):
        for w in self.workers:
            w.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)


def main(api):
    fs = api.fixture("rp_fx_simple", SIMPLE)
    e = api.exp({"A": ["rp_fx_simple:f"], "B": ["rp_fx_simple:g"]}, sections={"A": "A", "B": "B"})

    def run(c):
        async def drive():
            pool = Pool()
            a_done, b_done = asyncio.Event(), asyncio.Event()

            async def a():
                await pool.submit(fs.g)
                a_done.set()
                await b_done.wait()

            async def b():
                await pool.submit(fs.f)
                fs.g()

            async def gate_b():
                await a_done.wait()
                try:
                    await c.run_async("B", b)
                finally:
                    b_done.set()
            res = await asyncio.gather(c.run_async("A", a), gate_b(), return_exceptions=True)
            await pool.close()
            return [type(x).__name__ if isinstance(x, BaseException) else None for x in res]
        return str(asyncio.run(drive()))
    return {"T12": api.trace(e, run)}
