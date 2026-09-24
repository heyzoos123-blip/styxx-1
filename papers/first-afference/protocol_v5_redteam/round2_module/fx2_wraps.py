import functools
def _run(x, mode): return (x, mode)
@functools.wraps(_run)
def run_fast(x): return _run(x, "fast")
@functools.wraps(_run)
def run_safe(x): return _run(x, "safe")
