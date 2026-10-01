"""round4/attribution/r1/a02_eager_nested.py, rewritten: run_async section A's work gathers three children that
each open their own run_async section B, under the default task factory and under asyncio.eager_task_factory
(3.12+; on older versions the eager half is recorded as absent)."""
import asyncio


def main(api):
    fx = api.fixture("rp_a02_fix", "def f(): return 1\ndef g(): return 2\n")
    e = api.exp({"A": ["rp_a02_fix:f"], "B": ["rp_a02_fix:g"]}, sections={"A": "A", "B": "B"})
    out = {}
    for eager in (False, True):
        if eager and not hasattr(asyncio, "eager_task_factory"):
            out["eager"] = "absent"
            continue

        def harness(c):
            async def job():
                fx.g()
                await asyncio.sleep(0)

            async def gate_a():
                fx.f()
                await asyncio.gather(*(c.run_async("B", job) for _ in range(3)))

            async def drive():
                if eager:
                    asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
                await c.run_async("A", gate_a)
            asyncio.run(drive())
        out["eager" if eager else "default"] = api.trace(e, harness)
    return out
