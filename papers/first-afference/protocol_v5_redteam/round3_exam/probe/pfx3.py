import functools
def _run(): return 12
@functools.wraps(_run)
def run_fast(): return _run()
@functools.wraps(_run)
def run_safe(): return _run()
