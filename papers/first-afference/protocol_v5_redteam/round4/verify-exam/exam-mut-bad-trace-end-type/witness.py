"""Witness: a genuine trace (f ran in section G) whose one opening's `end` is replaced by a str
subclass equal to "returned" -- the only non-exact type in the trace. Spec step 3: "Every type
check is exact (type(x) is ...)". Original: BAD_TRACE. Mutant (`o["end"] not in _ENDS` only): PASS.
A second variant uses a str subclass whose __eq__/__hash__ make it compare equal to "returned"
while its text is "finished" (the X101 value): original BAD_TRACE, mutant PASS."""
import sys, json
sys.path.insert(0, "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/verify-exam")
from b7lib import both
MUT = "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/verify-exam/exam-mut-bad-trace-end-type"
BODY = r'''
import copy
mod = mkmod("b7et_fx", "def f():\n    return 1\n")
exp = mkexp({"G": {"exercises": ["b7et_fx:f"]}})
with coverage_trace(exp) as cov:
    cov.run("G", mod.f)
rec = cov.record()
class Tagged(str):
    pass
class Liar(str):
    def __eq__(self, other): return True
    def __ne__(self, other): return False
    def __hash__(self): return hash("returned")
r1 = copy.deepcopy(rec); r1["sections"]["G"][0]["end"] = Tagged("returned")
r2 = copy.deepcopy(rec); r2["sections"]["G"][0]["end"] = Liar("finished")
out(plain=score(exp, copy.deepcopy(rec)), subclass_returned=score(exp, r1), liar_finished=score(exp, r2),
    check_metrics_r1=exp.check_metrics({"m": 1.0, "coverage_trace": r1}).get("G:exercises"))
'''
o, m = both(MUT, BODY)
sep = (o["subclass_returned"].get("refused", "").startswith("[V5:BAD_TRACE]")
       and m["subclass_returned"].get("verdict") == "PASS")
print("SEPARATES" if sep else "NO SEPARATION")
