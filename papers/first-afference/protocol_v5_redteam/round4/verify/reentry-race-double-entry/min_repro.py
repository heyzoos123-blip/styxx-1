"""Minimal entry point: runs own_repro.py scenarios A (control), B (shared tracer, first import of
the declared module), D (same, while a separate legitimate outer tracer holds the mint) and E
(check passed before the first thread's exit -> an exited tracer is re-activated), each in a
fresh process. Run: PYTHONPATH=/home/user/styxx-1 python min_repro.py"""
import os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
for s in "ABDE":
    r = subprocess.run([sys.executable, os.path.join(here, "own_repro.py"), s],
                       capture_output=True, text=True, timeout=60)
    print(r.stdout + r.stderr)
