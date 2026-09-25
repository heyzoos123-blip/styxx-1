"""Witness: examhole-cache-body-module-check. A cache wrapper held OUTSIDE vars(mod) whose body is
bound at module level; the section calls only the module-level body, never the declared wrapper."""
import importlib
from b3lib import write_module, trace_and_score, leftovers, emit

write_module("b3cache", '''
import functools

def _impl(x): return x * 2                  # the body, bound by name at module level

class Scorer:
    fast = staticmethod(functools.lru_cache(None)(_impl))    # class-held wrapper (staticmethod)
    fast2 = functools.lru_cache(None)(_impl)                 # class-held wrapper (bare)

def _impl3(x): return x + 3                 # body of a wrapper served only by PEP 562 (holder None)
_LAZY = {"lazy_fast": functools.lru_cache(None)(_impl3)}

def __getattr__(name):
    if name in _LAZY:
        return _LAZY[name]
    raise AttributeError(name)
''')
m = importlib.import_module("b3cache")
out = {}
# the declared wrapper is never called; only the module-level body is
out["class_staticmethod_wrapper_body_called_directly"] = trace_and_score(
    {"G": ["b3cache:Scorer.fast"]}, {"G": lambda: m._impl(1)})
out["class_bare_wrapper_body_called_directly"] = trace_and_score(
    {"G": ["b3cache:Scorer.fast2"]}, {"G": lambda: m._impl(2)})
out["pep562_wrapper_body_called_directly"] = trace_and_score(
    {"G": ["b3cache:lazy_fast"]}, {"G": lambda: m._impl3(3)})
# control: the wrapper IS called (the original still refuses: the rule is structural)
Scorer = m.Scorer
Scorer.fast.cache_clear()
out["class_wrapper_called_control"] = trace_and_score(
    {"G": ["b3cache:Scorer.fast"]}, {"G": lambda: Scorer.fast(5)})
Scorer.fast.cache_clear()
out["leftovers"] = leftovers()
emit(out)
