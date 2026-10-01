"""Fixture sources for the round-3 module repros (round3_module/fx3_*.py, copied; module names prefixed rp_)."""
CLONE = '''
import types
def target(x): return x * 3
REGISTRY = []
def make_variant():
    f = types.FunctionType(target.__code__, target.__globals__, "variant")
    REGISTRY.append(f)
    return f
'''
FACTORY = '''
def make_mul(k):
    return lambda x, k=k: x * k
double = make_mul(2)

def make_scorer(metric, strict):
    def score(x, strict=strict):
        v = metric(x)
        if strict and v < 0:
            raise ValueError("negative")
        return v
    return score
score_lenient = make_scorer(abs, False)
'''
FRAMES = '''
import asyncio
class Base:
    def fit(self, x): return x
class Model(Base):
    def fit(self, x):
        return super().fit(x) + 1
def _mk_gen(k):
    def gen(n):
        for i in range(n):
            yield i + k
    return gen
gen = _mk_gen(10)
def _mk_coro(k):
    async def coro(n):
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return n + k
    return coro
coro = _mk_coro(5)
def _mk_cellarg(k):
    def cellarg(x):
        return list(map(lambda y: x + y + k, [1, 2]))
    return cellarg
cellarg = _mk_cellarg(100)
def _mk_lazy():
    cache = None
    def get():
        nonlocal cache
        if cache is None:
            cache = [1, 2, 3]
        return cache
    return get
get = _mk_lazy()
def _mk_rec():
    def walk(n):
        return 0 if n == 0 else 1 + walk(n - 1)
    return walk
walk = _mk_rec()
'''
NS = '''
import types
def _a(x): return x
ops = types.SimpleNamespace(a=_a)
class _Registry: pass
reg = _Registry(); reg.a = _a
def __getattr__(name):
    if name == "lazy_a": return _a
    raise AttributeError(name)
'''
PERF = '''
def plain(x): return x
def _mk():
    a = 1; b = 2; c = 3
    def clos(x): return x + a + b + c
    return clos
clos = _mk()
def _mk_big():
    big = list(range(10))
    def bigloc(x):
        l0=l1=l2=l3=l4=l5=l6=l7=l8=l9=l10=l11=l12=l13=l14=l15=l16=l17=l18=l19=x
        return x + big[0]
    return bigloc
bigloc = _mk_big()
'''
WRAPS = '''
import functools
def _run(x, mode): return (x, mode)
@functools.wraps(_run)
def run_fast(x):
    return _run(x, "fast")
def run_safe(x): return _run(x, "safe")

class Timed:
    def __init__(self, fn, label):
        functools.update_wrapper(self, fn); self.fn = fn; self.label = label
    def __call__(self, *a): return self.fn(*a)
def _impl(x): return x * 2
fast = Timed(_impl, "fast")
safe = Timed(_impl, "safe")

def retrying(fn):
    @functools.wraps(fn)
    def w(*a):
        return fn(*a)
    return w
def _core(x): return x + 1
@functools.wraps(_core)
def public(x):
    return _core(x)
def other_entry(x):
    return retrying(_core)(x)

def score(x): return x
def deprecated(fn):
    @functools.wraps(fn)
    def w(*a): return fn(*a)
    return w
score_v1 = deprecated(score)
score_legacy = deprecated(score)
'''
SIMPLE = '''
def f(): return 1
def g(): return 2
'''
