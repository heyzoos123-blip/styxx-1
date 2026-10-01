"""Fixture sources for the round-2 module repros (round2_module/fx2_*.py, copied; module names prefixed rp_)."""
CLONE = '''
import types
def target(x): return x * 3
def other(x): return x - 1
'''
CYC = '''
def _make(limit):
    def walk(n):                 # a recursive closure: walk -> cell -> walk is a reference cycle
        return 0 if n >= limit else 1 + walk(n + 1)
    return walk
walk10 = _make(10)
def warmup():                    # builds and drops a temporary walker
    w = _make(3); w(0)
warmup()
'''
INST = '''
class Base:
    def fit(self): return 1
class Sub(Base): pass
class Other(Base): pass
default_model = Sub()
'''
MANY = "".join(f"def t{i}(): return {i}\n" for i in range(40))
REC = '''
def depth(n):
    return 0 if n == 0 else 1 + depth(n - 1)
def parse(s):
    return depth(len(s))
'''
SD = '''
import functools
@functools.singledispatch
def process(x): return ("generic", x)
@process.register
def _(x: int): return ("int", x)
'''
TIMED = '''
def timed(fn):
    def wrapper(*a, **k):
        return fn(*a, **k)
    return wrapper

@timed
def score_all(x):
    return x * 2

def cheap_path(x):
    return x + 1

def get_cheap_handler():
    return timed(cheap_path)
'''
PLUGIN = '''
import rp_fx2_timed
@rp_fx2_timed.timed
def plugin_entry(x):
    return -x
'''
WRAPS = '''
import functools
def _run(x, mode): return (x, mode)
@functools.wraps(_run)
def run_fast(x): return _run(x, "fast")
@functools.wraps(_run)
def run_safe(x): return _run(x, "safe")
'''
SIMPLE = '''
import time
def f(): return 1
def g(): return 2
def slow_then_g(delay=0.2):
    time.sleep(delay); return g()
async def af(): return f()
def gen():
    yield g()
'''
