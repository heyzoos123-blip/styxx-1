# ---- self-contained prelude (identical in every script of this lens) ----
import json, os, subprocess, sys, tempfile, textwrap, threading, types
from pathlib import Path
sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

_TMP = Path(tempfile.mkdtemp(prefix="rt4id_"))
sys.path.insert(0, str(_TMP))

def write_mod(name, src):
    (_TMP / f"{name}.py").write_text(textwrap.dedent(src), encoding="utf-8")
    sys.modules.pop(name, None)

def make_exp(**gates):
    d = Path(tempfile.mkdtemp(prefix="rt4id_repo_"))
    g = {k: {"metric": "m", "op": ">=", "value": 0.5, **v} for k, v in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {k: True for k in g}, "verdict": "PASS"},
                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = d / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=d, check=True)
    return Experiment(p)

def score(exp, rec, m=1.0):
    try:
        v = exp.score({"m": m, "coverage_trace": rec})
        return f"PASS verdict={v.verdict} coverage={v.coverage}"
    except GateSpecError as e:
        return f"REFUSED {str(e)[:220]}"

def leftovers():
    return dict(profile=sys.getprofile(), minted=len(P._MINTED), by_fn=len(P._BY_FN),
                anchors=len(P._ANCHORS), threads=len(P._THREADS), active=P._ACTIVE)
# ---- end prelude ----
# ATTACK 01: a stub installed IN PLACE, by assigning the stub's code to the real function's
# __code__ before the trace ("patch everywhere, including captured `from m import f` aliases").
# The function object is the real one (its __globals__ IS the declared module's dict), so
# FOREIGN_DEFINITION passes although the code comes from the test module. The real body never
# runs; the gate PASSES.
write_mod("rt4_power", """
    def reachable(n):
        # the real, expensive computation
        return sum(i * i for i in range(n)) > 10
""")
write_mod("rt4_teststubs", """
    def fake_reachable(n):
        return True          # stub: the real body is never executed
""")
import rt4_power, rt4_teststubs
from rt4_power import reachable as captured   # harness pre-binds an alias, as run_p1 does

# harness setup, BEFORE the trace: stub the function in place so the captured alias sees it too
original_code = rt4_power.reachable.__code__
rt4_power.reachable.__code__ = rt4_teststubs.fake_reachable.__code__

exp = make_exp(G={"exercises": ["rt4_power:reachable"]})
real_body_ran = []
with coverage_trace(exp) as cov:
    r = cov.run("G", lambda: [captured(n) for n in range(3)])
rec = cov.record()
out = score(exp, rec)
rt4_power.reachable.__code__ = original_code

# variant b: a stub function BUILT with the declared module's globals and bound at the name
# before the trace (code from the test module, globals from the declared module).
write_mod("rt4_power_b", """
    def reachable(n):
        return sum(i * i for i in range(n)) > 10
""")
import rt4_power_b
rt4_power_b.reachable = types.FunctionType(rt4_teststubs.fake_reachable.__code__,
                                           vars(rt4_power_b), "reachable")
exp_b = make_exp(G={"exercises": ["rt4_power_b:reachable"]})
with coverage_trace(exp_b) as cov:
    cov.run("G", rt4_power_b.reachable, 3)
out_b = score(exp_b, cov.record())
print("variant b (FunctionType(stub_code, vars(mod))):", out_b)
print("trace targets:", rec["targets"])
print("sections:", rec["sections"])
print("score:", out)
if out.startswith("PASS") and r == [True, True, True]:
    print("FINDING-REPRODUCED: a stub from another module installed by pre-trace __code__ "
          "assignment passes FOREIGN_DEFINITION and the gate PASSES although the declared body "
          f"never ran (targets provenance even names {rec['targets']['rt4_power:reachable']})")
else:
    print("no finding: code-swap stub refused ->", out)
