# R2-B2's shape with asyncio instead of threads: a lazily created pool of consumer TASKS (a common
# asyncio worker-queue pattern) is started by whichever section first needs it. Tasks copy the
# creating context, so the workers carry section A's ContextVar value -> attribution via "context",
# which the ambiguity rule does not cover. Gate A declares f; A's own work never calls f; B's
# pooled job, executed by A-created workers while both sections are open, calls f; B declares g
# and calls it directly.
import asyncio
from rtlib import *
import fx_simple
class Pool:
    def __init__(self): self.q = None; self.workers = []
    async def submit(self, fn):
        if self.q is None:                       # lazy start by the first caller
            self.q = asyncio.Queue()
            self.workers = [asyncio.create_task(self._work()) for _ in range(2)]
        fut = asyncio.get_running_loop().create_future()
        await self.q.put((fn, fut)); return await fut
    async def _work(self):
        while True:
            fn, fut = await self.q.get(); fut.set_result(fn())
    async def close(self):
        for w in self.workers: w.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
def run():
    e = exp(spec(A={"exercises": ["fx_simple:f"]}, B={"exercises": ["fx_simple:g"]}))
    pool = Pool()
    async def gate_a(cov):
        with cov.section("A"):
            await pool.submit(fx_simple.g)       # A's work: g only (never f)
            await asyncio.sleep(0.2)
    async def gate_b(cov):
        await asyncio.sleep(0.05)
        with cov.section("B"):
            await pool.submit(fx_simple.f)       # B's pooled job: f
            fx_simple.g()                        # B's own direct work: g
    async def main(cov):
        await asyncio.gather(gate_a(cov), gate_b(cov)); await pool.close()
    with coverage_trace(e) as cov:
        asyncio.run(main(cov))
    r = cov.record(); print("   sections:", r["sections"], "ambiguous:", r["ambiguous"])
    return score(e, r)
attempt("T12 asyncio worker tasks created by A run B's job while both open", run)
