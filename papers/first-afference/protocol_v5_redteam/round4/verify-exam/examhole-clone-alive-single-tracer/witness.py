"""Witness: nested tracers share f's mint. The INNER section calls ONLY a same-globals clone of
f's minted code (f itself never runs) and keeps the clone alive past the inner exit; it is
dropped before the outer exit. Spec __exit__ step 4: every tracer runs the refcount check + scan
for each distinct mint -> the inner trace must record CLONE_ALIVE."""
import sys, types
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__file__)))
from wcommon import *                                        # noqa: F401,F403

e_out, e_in = exp({"G": [T("f")]}), exp({"H": [T("f")]})
orig = FX.f.__code__
keep = []
with coverage_trace(e_out) as outer:
    with coverage_trace(e_in) as inner:
        def body():
            clone = types.FunctionType(FX.f.__code__, FX.f.__globals__)   # same globals: credited as f
            keep.append(clone)
            return clone(1)
        inner.run("H", body)
    rec_in = inner.record()
    keep.clear()                     # dropped before the outer exit, so the outer trace is clean
rec_out = outer.record()
emit({"inner_problems": [p[:40] for p in rec_in["problems"]],
      "inner_verdict": outcome(e_in, rec_in),
      "outer_problems": [p[:40] for p in rec_out["problems"]],
      "outer_verdict": outcome(e_out, rec_out),
      "code_restored": FX.f.__code__ is orig, "leftovers": leftovers()})
