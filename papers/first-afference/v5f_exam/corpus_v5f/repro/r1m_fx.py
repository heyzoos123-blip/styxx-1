"""Shared fixture sources for the round-1 module repros (round1_module/fx_*.py, copied verbatim; fx_simple's
slow_then_g takes an event to wait on instead of a sleep, so the interleaving is fixed)."""
SIMPLE = '''
import time
def f(): return 1
def g(): return 2
def slow_then_g(delay=0.2, ev=None):
    if ev is not None:
        ev.wait(10)
    else:
        time.sleep(delay)
    return g()
async def af(): return f()
def gen():
    yield g()
'''
CM = '''
class K:
    @classmethod
    def make(cls): return cls()
    def __call__(self): return 7
def boom(): raise ValueError("x")
def rec(n): return 0 if n == 0 else rec(n - 1)
'''
MISC = '''
import functools
@functools.lru_cache(maxsize=None)
def cached_bar(n):
    return n * 2
def real(): return 1
'''
BROKEN = '''
raise RuntimeError("optional backend not configured")   # e.g. a module that fails at import
def f(): pass
'''
CYCLE = '''
def f(): return 1
f.__wrapped__ = f          # e.g. a sloppy self-referential wrapper
'''
SYNTAX = '''
def f(:
    pass
'''
