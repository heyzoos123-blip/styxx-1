"""Witness: nested tracers share f's mint (outer first in m.tracers). The INNER section runs
FunctionType(f.__code__, {})(1) and f(1). Spec hook: 'for t in tracers: t._clone_called.add' ->
the inner trace must record CLONE_CALLED and refuse its gate."""
import sys, types
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__file__)))
from wcommon import *                                        # noqa: F401,F403

e_out, e_in = exp({"G": [T("f")]}), exp({"H": [T("f")]})
orig = FX.f.__code__
with coverage_trace(e_out) as outer:
    with coverage_trace(e_in) as inner:
        inner.run("H", lambda: (types.FunctionType(FX.f.__code__, {})(1), FX.f(1)))
    rec_in = inner.record()
    outer.run("G", FX.f, 2)
rec_out = outer.record()
# control: the reverse nesting role -- the clone is called in the OUTER's section while an inner
# tracer is active; both tracers hold the mint.
e3, e4 = exp({"G": [T("f")]}), exp({"H": [T("f")]})
with coverage_trace(e3) as o3:
    with coverage_trace(e4) as i4:
        o3.run("G", lambda: (types.FunctionType(FX.f.__code__, {})(1), FX.f(1)))
        i4.run("H", FX.f, 1)
    rec4 = i4.record()
rec3 = o3.record()
emit({"inner_problems": [p[:40] for p in rec_in["problems"]],
      "inner_verdict": outcome(e_in, rec_in),
      "outer_problems": [p[:40] for p in rec_out["problems"]],
      "outer_verdict": outcome(e_out, rec_out),
      "ctrl_outer_section_clone__outer_verdict": outcome(e3, rec3),
      "ctrl_outer_section_clone__inner_verdict": outcome(e4, rec4),
      "code_restored": FX.f.__code__ is orig, "leftovers": leftovers()})
