"""round4/identity/r1/a02_cache_wrapped_restamped.py and a03_two_cache_wrappers_one_body.py, rewritten: a02 (a)
an lru_cache wrapper re-stamped by functools.wraps(Ref.power) (its __wrapped__ names a function the cache never
calls), only Ref.power called; (b) only the declared power called; (c) the same stacking with the reference at
module level, entered. a03: two distinct lru_cache wrappers around one unnamed body, section S calls only
cached_all while its gate declares cached_small."""

A02 = '''
import functools
class Ref:
    @staticmethod
    def power(n):
        return sum(range(n))
@functools.wraps(Ref.power)
@functools.lru_cache(maxsize=None)
def power(n):
    return n * (n - 1) // 2
'''
A02C = '''
import functools
def reference(n):
    return sum(range(n))
@functools.wraps(reference)
@functools.lru_cache(maxsize=None)
def fast(n):
    return n * (n - 1) // 2
'''
A03 = '''
import functools
def _two_caches(fn):
    return functools.lru_cache(maxsize=None)(fn), functools.lru_cache(maxsize=16)(fn)
def _score(x):
    return x * 2
cached_all, cached_small = _two_caches(_score)
del _score
'''


def main(api):
    cm = api.fixture("rp_id_cachemod", A02)
    e = api.exp({"G": ["rp_id_cachemod:power"]})
    out = {"a02_a_only_reference": api.trace(e, lambda c: c.run("G", cm.Ref.power, 10))}
    cm.power.cache_clear()
    out["a02_b_only_declared"] = api.trace(e, lambda c: c.run("G", cm.power, 10))
    api.fixture("rp_id_cachemod_c", A02C)
    out["a02_c_module_level_reference"] = api.trace(api.exp({"G": ["rp_id_cachemod_c:fast"]}))
    tc = api.fixture("rp_id_twocache", A03)
    e = api.exp({"G_ALL": ["rp_id_twocache:cached_all"], "G_SMALL": ["rp_id_twocache:cached_small"]},
                sections={"G_ALL": "A", "G_SMALL": "S"})
    out["a03_two_wrappers"] = api.trace(e, lambda c: c.run("A", tc.cached_all, 1), lambda c: c.run("S", tc.cached_all, 2))
    ci = tc.cached_small.cache_info()
    out["a03_cached_small_calls"] = ci.hits + ci.misses
    return out
