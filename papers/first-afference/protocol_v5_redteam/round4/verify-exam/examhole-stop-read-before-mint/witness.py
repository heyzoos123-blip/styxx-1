"""Witness: a gate declares asyncio.events:Handle._run AND f; the loop runs INSIDE the section
(cov.run('A', asyncio.run, main())), X73's shape. Spec: _STOP is read after minting, so the cut
is the minted Handle._run code that actually runs -> f is 'dispatched', gate NOT_EXERCISED."""
import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__file__)))
from wcommon import *                                        # noqa: F401,F403
import asyncio.events

h_orig = asyncio.events.Handle._run.__code__
e = exp({"A": ["asyncio.events:Handle._run", T("f")]})
with coverage_trace(e) as cov:
    stop_during = P._STOP
    stop_is_running_code = P._STOP is asyncio.events.Handle._run.__code__
    cov.run("A", asyncio.run, FX.amain())
rec = cov.record()
out = {"_STOP_is_Handle._run_current_code_during_trace": stop_is_running_code,
       "_STOP_is_original_code": stop_during is h_orig,
       "uncredited": rec["uncredited"], "A_calls": [o["calls"] for o in rec["sections"]["A"]],
       "verdict": outcome(e, rec),
       "handle_code_restored": asyncio.events.Handle._run.__code__ is h_orig,
       "leftovers_after": leftovers()}
# secondary: a refused __enter__ (UNRESOLVED target) must not leave _STOP set
e2 = exp({"A": [T("no_such_fn")]})
try:
    coverage_trace(e2).__enter__()
    out["refused_enter"] = "NOT REFUSED"
except GateSpecError as ex:
    out["refused_enter"] = str(ex)[:20]
out["leftovers_after_refused_enter"] = leftovers()
emit(out)
