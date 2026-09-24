from rtlib import *
import fx_simple as fx, fx_misc, asyncio, time
from unittest import mock
def attempt(label, fn):
    try: print(label, "->", fn())
    except GateSpecError as ex: print(label, "-> GateSpecError:", str(ex)[:110])
    except BaseException as ex: print(label, "-> ESCAPED", type(ex).__name__, str(ex)[:100])

# (a) asyncio task created in section A, run by the loop while section B is open
e = exp(spec(A={"exercises": ["fx_simple:g"]}, B={"exercises": ["fx_simple:f"]}))
async def main(cov):
    with cov.section("A"):
        fx.g()
        task = asyncio.get_running_loop().create_task(fx.af())   # A's background task
    with cov.section("B"):
        await asyncio.sleep(0.05)                                # B itself never calls f
    await task
with coverage_trace(e) as cov:
    asyncio.run(main(cov))
print("(a) asyncio task from A counted in B:", score(e, cov.record()))

# (b) lru_cache: both gates really call the declared function; the second hits the cache
e = exp(spec(A={"exercises": ["fx_misc:cached_bar"]}, B={"exercises": ["fx_misc:cached_bar"]}))
with coverage_trace(e) as cov:
    with cov.section("A"): fx_misc.cached_bar(3)
    with cov.section("B"): fx_misc.cached_bar(3)
print("(b) lru_cache second section:", score(e, cov.record()))

# (c) the target is patched with a Mock while the trace is constructed (test-suite harness)
e = exp(spec(G={"exercises": ["fx_misc:real"]}))
with mock.patch("fx_misc.real"):
    attempt("(c) coverage_trace under mock.patch", lambda: coverage_trace(e))

# (d) backward compat: a v4-valid gate carrying 'section' / 'exercises' as free-text annotations
for extra in ({"section": "see prose section 3.2"}, {"exercises": "the reachable() path"}):
    attempt(f"(d) Experiment with {extra}", lambda: exp(spec(G=extra)).score({"m": 1.0}).verdict)
