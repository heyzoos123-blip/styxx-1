"""Witness: examhole-module-step-exact-type. Modules whose type is a ModuleType SUBCLASS."""
import importlib, importlib.util, sys
from b3lib import write_module, trace_and_score, leftovers, emit

# (a) a module that swaps its own __class__ to a ModuleType subclass (the documented recipe for
#     module-level properties) and serves one target lazily through PEP 562 __getattr__.
write_module("b3modsub", '''
import sys, types

def direct(): return 1

def _helper(): return 5

def __getattr__(name):
    if name == "helper":
        return _helper
    raise AttributeError(name)

class _Mod(types.ModuleType):
    @property
    def version(self): return "1.0"

sys.modules[__name__].__class__ = _Mod
''')
# (b) a package whose SUBMODULE has a ModuleType-subclass class; the target reaches the submodule
#     after the colon (spec: a module reached later refuses INSTANCE_PATH).
write_module("b3pkg/__init__", '''
from . import sub

def fn(): return 1

sub.fn = fn
''')
write_module("b3pkg/sub", '''
import sys, types
class _Mod(types.ModuleType):
    pass
sys.modules[__name__].__class__ = _Mod
''')
# (c) the stdlib importlib.util.LazyLoader recipe
write_module("b3lazy", '''
def work(): return 9
''')

out = {}
m = importlib.import_module("b3modsub")
out["type_of_module_a"] = type(m).__name__
out["modsub_pep562_target"] = trace_and_score({"G": ["b3modsub:helper"]}, {"G": lambda: m.helper()})
out["modsub_direct_target_control"] = trace_and_score({"G": ["b3modsub:direct"]}, {"G": lambda: m.direct()})

pkg = importlib.import_module("b3pkg")
out["type_of_submodule_b"] = type(pkg.sub).__name__
out["module_after_colon_subclassed"] = trace_and_score({"G": ["b3pkg:sub.fn"]}, {"G": lambda: pkg.sub.fn()})

spec = importlib.util.find_spec("b3lazy")
loader = importlib.util.LazyLoader(spec.loader)
spec.loader = loader
lm = importlib.util.module_from_spec(spec)
sys.modules["b3lazy"] = lm
loader.exec_module(lm)
out["type_of_lazy_module_before"] = type(lm).__name__
out["lazyloader_target"] = trace_and_score({"G": ["b3lazy:work"]}, {"G": lambda: sys.modules["b3lazy"].work()})
out["leftovers"] = leftovers()
emit(out)
