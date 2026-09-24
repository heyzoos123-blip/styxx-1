# a module whose public entry points come from a factory (shared code object)
def _make(k):
    def check(x):
        return x > k
    return check
check_low = _make(0.1)
check_high = _make(0.9)

def plain(f):          # decorator without functools.wraps
    def inner(*a, **k):
        return f(*a, **k)
    return inner

@plain
def entry_a(): return "a"
@plain
def entry_b(): return "b"
