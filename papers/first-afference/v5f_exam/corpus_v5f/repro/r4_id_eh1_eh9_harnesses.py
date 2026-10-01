"""round4/identity/r1/eh1_walk_bound_2_hops.py through eh9_no_module_body_check.py, rewritten: each file's paired
harness (its HARNESS program, the half that runs against the public API). Their other half (building a v5e
mutant and running v5e's frozen exam on it) is exam tooling for v5e (NOT_APPLICABLE.json).
eh1 three stacked functools.wraps decorators from another module; eh2 nested tracers, the inner calls only a
same-globals clone kept alive past the inner exit; eh3 nested tracers, the inner runs a foreign-globals clone;
eh4 nested tracers, the inner hot-swaps f.__code__ and leaves it; eh5 a gate declaring asyncio.events:Handle._run
and f with the loop run inside the section; eh6 methods of ABC and Enum classes; eh7 a ModuleType-subclass module's
PEP 562 helper; eh8 a method inherited from a grandparent; eh9 a class-held cache wrapper whose body is bound at
module level, only the body called."""
import asyncio, asyncio.events, types

DECOS = '''
import functools
def retry(fn):
    @functools.wraps(fn)
    def w(*a, **k): return fn(*a, **k)
    return w
def log_calls(fn):
    @functools.wraps(fn)
    def w(*a, **k): return fn(*a, **k)
    return w
def timed(fn):
    @functools.wraps(fn)
    def w(*a, **k): return fn(*a, **k)
    return w
'''
SVC = '''
from rp_eh_decos import retry, log_calls, timed
@retry
@log_calls
@timed
def fetch(x):
    return x + 1
'''
ABC = '''
import abc, enum
class Model(abc.ABC):
    def fit(self, x):
        return x + 1
    @abc.abstractmethod
    def predict(self, x): ...
class Lin(Model):
    def predict(self, x):
        return 2 * x
class Color(enum.Enum):
    RED = 1
    def describe(self):
        return self.name.lower()
'''
MODSUB = '''
import sys, types
def _make_helper():
    def helper(x=0):
        return x + 1
    return helper
def __getattr__(name):
    if name == "helper":
        fn = _make_helper()
        globals()["helper"] = fn
        return fn
    raise AttributeError(name)
class _Mod(types.ModuleType):
    @property
    def version(self):
        return "1.0"
sys.modules[__name__].__class__ = _Mod
'''
INH = '''
class Base:
    def fit(self, x):
        return x
class Mid(Base):
    pass
class Leaf(Mid):
    pass
'''
CLS_CACHE = '''
import functools
def _impl(x):
    return x * 3
class Scorer:
    fast = staticmethod(functools.lru_cache(maxsize=None)(_impl))
'''


def main(api):
    out = {}
    api.fixture("rp_eh_decos", DECOS)
    svc = api.fixture("rp_eh_svc", SVC)
    out["eh1"] = api.trace(api.exp({"G": ["rp_eh_svc:fetch"]}), lambda c: c.run("G", svc.fetch, 1))

    def nested(modname, inner_body):
        mn = api.fixture(modname, "def f(x=0): return x\ndef u(x=0): return -x\n")
        F0 = mn.f.__code__
        eo, ei = api.exp({"O": [f"{modname}:f"]}), api.exp({"I": [f"{modname}:f"]})
        keep, box = [], {}

        def outer_h(c):
            box["inner"] = api.trace(ei, lambda ic: ic.run("I", inner_body, mn, keep))
            keep.clear()
            c.run("O", mn.f, 1)
        r = {"outer": api.trace(eo, outer_h)}
        r["inner"] = box.get("inner")
        mn.f.__code__ = F0
        return r

    def eh2(mn, keep):
        clone = types.FunctionType(mn.f.__code__, mn.f.__globals__, "f_copy")
        keep.append(clone)
        clone(1)
    out["eh2"] = nested("rp_eh_nest", eh2)
    out["eh3"] = nested("rp_eh_nest3", lambda mn, keep: (mn.f(1), types.FunctionType(mn.f.__code__, {})(1)) and None)

    def eh4(mn, keep):
        mn.f(1)
        mn.f.__code__ = mn.u.__code__
    out["eh4"] = nested("rp_eh_swap", eh4)
    ml = api.fixture("rp_eh_loopcut", "def f(x=0): return x\n")

    async def child():
        ml.f(1)

    async def amain():
        await asyncio.gather(child(), child())
    out["eh5"] = api.trace(api.exp({"A": ["asyncio.events:Handle._run", "rp_eh_loopcut:f"]}),
                           lambda c: c.run("A", asyncio.run, amain()))
    ma = api.fixture("rp_eh_abc", ABC)
    out["eh6"] = api.trace(api.exp({"G": ["rp_eh_abc:Model.fit", "rp_eh_abc:Lin.predict", "rp_eh_abc:Color.describe"]}),
                           lambda c: c.run("G", lambda: (ma.Lin().fit(1), ma.Lin().predict(1), ma.Color.RED.describe()) and None))
    ms = api.fixture("rp_eh_modsub", MODSUB)
    out["eh7"] = api.trace(api.exp({"G": ["rp_eh_modsub:helper"]}), lambda c: c.run("G", lambda: ms.helper(1)))
    api.fixture("rp_eh_inh", INH)
    out["eh8"] = api.trace(api.exp({"G": ["rp_eh_inh:Leaf.fit"]}))
    cc = api.fixture("rp_eh_cls_cache", CLS_CACHE)
    out["eh9"] = api.trace(api.exp({"G": ["rp_eh_cls_cache:Scorer.fast"]}), lambda c: c.run("G", cc._impl, 1))
    return out
