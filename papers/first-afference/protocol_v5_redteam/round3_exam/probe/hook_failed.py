import sys, types
from common import *
fx = types.ModuleType("fxm"); exec("def target(): return 1\ndef rec(n):\n    target()\n    return rec(n+1)\n", fx.__dict__); sys.modules["fxm"] = fx
e = exp_of({"G": {"exercises": ["fxm:target"]}})
try:
    with coverage_trace(e) as cov:
        with cov.section("G"):
            fx.target()
            try: fx.rec(0)
            except RecursionError: pass
except GateSpecError as ex:
    print("REFUSED", str(ex)[:120]); print("close_refusals", [m[:40] for m in cov.record()["close_refusals"]])
else:
    print("no refusal", cov.record()["sections"])
