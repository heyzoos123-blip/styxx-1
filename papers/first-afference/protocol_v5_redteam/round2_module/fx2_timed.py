# a module whose public entry point is wrapped by a decorator without functools.wraps
def timed(fn):
    def wrapper(*a, **k):
        return fn(*a, **k)
    return wrapper

@timed
def score_all(x):          # the declared target: resolves to timed.<locals>.wrapper's code
    return x * 2

def cheap_path(x):
    return x + 1

def get_cheap_handler():   # runtime decoration, e.g. a plugin/registry built on demand
    return timed(cheap_path)
