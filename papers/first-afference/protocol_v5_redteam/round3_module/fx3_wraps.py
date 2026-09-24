import functools
# R2-D2 shape, one wraps sibling removed: run_safe is an ordinary function that calls _run
def _run(x, mode): return (x, mode)
@functools.wraps(_run)
def run_fast(x):
    # the wrapper's own work (validation, caching...) is what the gate names
    return _run(x, "fast")
def run_safe(x): return _run(x, "safe")

# class-based decorator (update_wrapper on an instance): two siblings of one inner function
class Timed:
    def __init__(self, fn, label):
        functools.update_wrapper(self, fn); self.fn = fn; self.label = label
    def __call__(self, *a): return self.fn(*a)
def _impl(x): return x * 2
fast = Timed(_impl, "fast")
safe = Timed(_impl, "safe")

# per-call decoration with functools.wraps (retry-style), created inside a function
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
    return retrying(_core)(x)     # temporary wraps sibling, dead before section close

# undecorated target with two deprecated aliases (wraps)
def score(x): return x
def deprecated(fn):
    @functools.wraps(fn)
    def w(*a): return fn(*a)
    return w
score_v1 = deprecated(score)
score_legacy = deprecated(score)
