import functools
def target(): return 1
def _run2(): return 12
@functools.wraps(_run2)
def run_only(): return _run2()
def _timed(fn):
    def inner(*a, **k): return fn(*a, **k)
    return inner
def _impl(): return 10
score_all = _timed(_impl)
def cheap(): return 11
