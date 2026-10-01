"""round4/identity/r1/a06_pretrace_generator_objects.py, a07_gc_freeze_hides_clone.py and
a09_pep562_fresh_product.py, rewritten. a06: a generator object and coroutine objects created before the trace,
consumed (G) and awaited (H, run_async) inside sections. a07: a same-globals clone of the declared function made
and called in the section and kept alive at exit, with and without gc.freeze() after it was made (gc.unfreeze()
after). a09: a PEP 562 deprecation shim in the declared module returning a fresh wrapper per access, declared and
called in the section."""
import asyncio, gc, types, warnings

GEN = '''
def batches(n):
    for i in range(n):
        yield [i] * 3
async def fetch(x):
    return x * 2
'''
SHIM = '''
import warnings
def new_api(x):
    return x + 1
def __getattr__(name):
    if name == "old_api":
        def old_api(x):
            warnings.warn("old_api is deprecated; use new_api", DeprecationWarning, 2)
            return new_api(x)
        return old_api
    raise AttributeError(name)
'''


def main(api):
    out = {}
    mg = api.fixture("rp_id_gen", GEN)
    e = api.exp({"G": ["rp_id_gen:batches"], "H": ["rp_id_gen:fetch"]}, sections={"G": "G", "H": "H"})
    stream = mg.batches(4)
    coros = [mg.fetch(i) for i in range(3)]

    async def drive():
        return [await c for c in coros]
    out["a06"] = api.trace(e, lambda c: c.run("G", lambda: sum(len(b) for b in stream)),
                           lambda c: str(asyncio.run(c.run_async("H", drive))))
    mf = api.fixture("rp_id_frz", "def f(x=0): return x\ndef cheap(x=0): return 0\n")
    e = api.exp({"G": ["rp_id_frz:f"]})
    keep = []

    def body(freeze):
        clone = types.FunctionType(mf.f.__code__, mf.f.__globals__, "f_fast")
        keep.append(clone)
        clone(1)
        if freeze:
            gc.freeze()
    for freeze in (False, True):
        keep.clear()
        try:
            out[f"a07_freeze_{freeze}"] = api.trace(e, lambda c: c.run("G", body, freeze))
        finally:
            gc.unfreeze()
    keep.clear()
    ms = api.fixture("rp_id_shim", SHIM)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out["a09"] = api.trace(api.exp({"G": ["rp_id_shim:old_api"]}), lambda c: c.run("G", lambda: ms.old_api(1)))
    return out
