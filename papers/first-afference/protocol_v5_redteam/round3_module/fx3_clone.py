import types
def target(x): return x * 3
REGISTRY = []
def make_variant():
    # e.g. a registry/plugin system that copies a function to rebind defaults
    f = types.FunctionType(target.__code__, target.__globals__, "variant")
    REGISTRY.append(f)
    return f
