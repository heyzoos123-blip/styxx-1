"""Witness: nested tracers share f's mint. The INNER section calls f, then hot-swaps
f.__code__ = u.__code__ and leaves it in place through the inner exit (restored to the mint
before the outer exit, so the outer is clean). Spec __exit__ step 4: 'if fn.__code__ is not
m.code, record CODE_SWAPPED' for each tracer -> the inner trace must refuse CODE_SWAPPED."""
import sys, types
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__file__)))
from wcommon import *                                        # noqa: F401,F403

e_out, e_in = exp({"G": [T("f")]}), exp({"H": [T("f")]})
orig = FX.f.__code__
with coverage_trace(e_out) as outer:
    minted = FX.f.__code__
    with coverage_trace(e_in) as inner:
        def body():
            FX.f(1)
            FX.f.__code__ = FX.u.__code__          # hot swap, left in place
            FX.f(1)                                 # a call through the replacement: unobserved
        inner.run("H", body)
    rec_in = inner.record()
    FX.f.__code__ = minted
    outer.run("G", FX.f, 2)
rec_out = outer.record()
emit({"inner_problems": [p[:40] for p in rec_in["problems"]],
      "inner_verdict": outcome(e_in, rec_in),
      "outer_problems": [p[:40] for p in rec_out["problems"]],
      "outer_verdict": outcome(e_out, rec_out),
      "code_restored": FX.f.__code__ is orig, "leftovers": leftovers()})
