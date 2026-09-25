"""Witness: a profiler started INSIDE a section (spec over-block #6). Two variants:
 (a) a pure-Python profiler via sys.setprofile after f() and before g();
 (b) cProfile.Profile().enable() after f() and before g() (on 3.11 cProfile uses setprofile).
Original: the opening carries a PROFILER_LOST note and the NOT_EXERCISED refusal lists it.
Mutant (`sys.getprofile() is None`): no note; the refusal says nothing about the blind window."""
import sys, json
sys.path.insert(0, "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/verify-exam")
from b7lib import both
MUT = "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/verify-exam/exam-mut-profiler-lost-only-if-none"
BODY = r'''
import cProfile
mod = mkmod("b7pl_fx", "def f():\n    return 1\ndef g():\n    return 2\n")
exp = mkexp({"G": {"exercises": ["b7pl_fx:f", "b7pl_fx:g"]}})
def foreign(frame, event, arg):
    return None
prof = cProfile.Profile()
with coverage_trace(exp) as cov:
    def body_a():
        mod.f()
        sys.setprofile(foreign)          # a harness-started profiler, mid-section
        mod.g()
    cov.run("G", body_a)
    sys.setprofile(None)
    def body_b():
        mod.f()
        prof.enable()                    # cProfile around the second half of the section
        mod.g()
        # (left enabled until after the section closes, like a harness that profiles to the end)
    cov.run("G", body_b)
    prof.disable()
rec = cov.record()
out(notes=[[n[:32] for n in o["notes"]] for o in rec["sections"]["G"]],
    calls=[o["calls"] for o in rec["sections"]["G"]],
    score=score(exp, rec),
    leftover_profiler=repr(sys.getprofile()))
'''
o, m = both(MUT, BODY)
sep = (o.get("notes") != m.get("notes")
       and "PROFILER_LOST" in o["score"].get("refused", "")
       and "PROFILER_LOST" not in m["score"].get("refused", "PROFILER_LOST"))
print("SEPARATES" if sep else "NO SEPARATION")
