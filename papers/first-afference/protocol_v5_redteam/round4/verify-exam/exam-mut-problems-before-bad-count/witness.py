"""Witness: a trace carrying BOTH a recorded problem and a bad count. Spec score order: 6 BAD_COUNT
before 7 recorded problem. Original: BAD_COUNT. Mutant (problems block moved above the BAD_COUNT
loop): the problem's own code. Problems here are produced genuinely by the tracer
(UNDECLARED_SECTION swallowed by the harness; CLONE_CALLED via exec of the minted code); the bad
counts are edits (0, True, an undeclared key) -- the tracer itself never writes a bad count."""
import sys, json
sys.path.insert(0, "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/verify-exam")
from b7lib import both
MUT = "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/verify-exam/exam-mut-problems-before-bad-count"
BODY = r'''
import copy
mod = mkmod("b7pb_fx", "def f():\n    return 1\n")
exp = mkexp({"G": {"exercises": ["b7pb_fx:f"]}})
with coverage_trace(exp) as cov:
    try:
        cov.run("NOT_DECLARED", mod.f)          # refused and recorded; the harness swallows it
    except GateSpecError:
        pass
    cov.run("G", lambda: (mod.f(), exec(mod.f.__code__, {})))   # also records CLONE_CALLED
rec = cov.record()
def code(r):
    s = score(exp, r)
    return s.get("refused", "PASS " + str(s))[:40]
variants = {}
r = copy.deepcopy(rec); r["sections"]["G"][0]["calls"]["b7pb_fx:f"] = 0;    variants["count_0"] = code(r)
r = copy.deepcopy(rec); r["sections"]["G"][0]["calls"]["b7pb_fx:f"] = True; variants["count_True"] = code(r)
r = copy.deepcopy(rec); r["sections"]["G"][0]["ambiguous"]["b7pb_fx:zz"] = 1; variants["undeclared_key"] = code(r)
out(problems=[p[:30] for p in rec["problems"]], unedited=code(copy.deepcopy(rec)), variants=variants)
'''
o, m = both(MUT, BODY)
sep = all(v.startswith("[V5:BAD_COUNT]") for v in o["variants"].values()) and \
      all(v.startswith("[V5:UNDECLARED_SECTION]") for v in m["variants"].values())
print("SEPARATES" if sep else "NO SEPARATION")
