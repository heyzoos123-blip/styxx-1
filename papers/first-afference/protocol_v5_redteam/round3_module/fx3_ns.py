import types
def _a(x): return x
ops = types.SimpleNamespace(a=_a)          # namespace object holding plain functions
class _Registry: pass
reg = _Registry(); reg.a = _a
def __getattr__(name):                      # PEP 562 lazy attribute
    if name == "lazy_a": return _a
    raise AttributeError(name)
