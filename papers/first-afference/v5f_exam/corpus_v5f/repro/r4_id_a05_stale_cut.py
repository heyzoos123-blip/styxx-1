"""round4/identity/r1/a05_stale_stop_after_mint.py, rewritten: tracer A active; (control) section A runs
asyncio.run over two child tasks calling the declared f; (attack) an inner tracer declaring
asyncio.events:Handle._run is entered and exited (LIFO) inside A's trace first, then the same. _v5_state()'s
cut fields are read before each run; whether Handle._run's code is restored after."""
import asyncio, asyncio.events


def main(api):
    mc = api.fixture("rp_id_cut", "def f(x=0): return x\n")
    ORIG = asyncio.events.Handle._run.__code__
    expA = api.exp({"A": ["rp_id_cut:f"]})
    expB = api.exp({"B": ["asyncio.events:Handle._run"]})

    def program():
        async def child():
            mc.f(1)

        async def _main():
            await asyncio.gather(child(), child())
        return _main()
    out = {}
    for with_b in (False, True):
        r = {}

        def h(c):
            if with_b:
                r["inner"] = api.trace(expB)
            st = api.state()
            r["cut_current"] = st.get("cut_current")
            c.run("A", asyncio.run, program())
        r["trace"] = api.trace(expA, h)
        out["attack" if with_b else "control"] = r
    out["handle_run_restored"] = asyncio.events.Handle._run.__code__ is ORIG
    return out
