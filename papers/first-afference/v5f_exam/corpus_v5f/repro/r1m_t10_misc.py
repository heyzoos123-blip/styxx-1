"""round1_module/t10_misc.py, rewritten: (a) an asyncio task created in section A runs while section B's
coroutine awaits (run_async); (b) an lru_cache'd declared function called in two sections, the second a cache
hit; (c) the target patched with a Mock while the trace is constructed; (d) free-text 'section'/'exercises'
annotations (also in r1m_t09_t11_backcompat)."""
import asyncio


def main(api):
    from unittest import mock
    fx = api.fixture("rp_fx_simple", 'def f(): return 1\ndef g(): return 2\nasync def af(): return f()\n')
    misc = api.fixture("rp_fx_misc", 'import functools\n@functools.lru_cache(maxsize=None)\ndef cached_bar(n):\n'
                                     '    return n * 2\ndef real(): return 1\n')
    out = {}
    e = api.exp({"A": ["rp_fx_simple:g"], "B": ["rp_fx_simple:f"]}, sections={"A": "A", "B": "B"})
    box = {}

    async def a():
        fx.g()
        box["task"] = asyncio.get_running_loop().create_task(fx.af())

    async def b():
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def drive(c):
        await c.run_async("A", a)
        await c.run_async("B", b)
        await box["task"]
    out["a_asyncio_task_from_A"] = api.trace(e, lambda c: asyncio.run(drive(c)))
    e = api.exp({"A": ["rp_fx_misc:cached_bar"], "B": ["rp_fx_misc:cached_bar"]}, sections={"A": "A", "B": "B"})
    out["b_lru_cache"] = api.trace(e, lambda c: c.run("A", misc.cached_bar, 3), lambda c: c.run("B", misc.cached_bar, 3))
    e = api.exp({"G": ["rp_fx_misc:real"]})
    with mock.patch("rp_fx_misc.real"):
        out["c_under_mock_patch"] = api.trace(e)
    return out
