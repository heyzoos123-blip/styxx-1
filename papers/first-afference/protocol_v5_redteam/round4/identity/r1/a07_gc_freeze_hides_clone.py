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
# ATTACK 07: CLONE_ALIVE relies on gc.get_referrers(M_T), which scans only the three collectable
# generations. Objects moved to the permanent generation by gc.freeze() (a standard step before
# forking worker processes) are invisible to it. A same-globals clone of M_T built in the trace and
# KEPT ALIVE at exit (spec X57: CLONE_ALIVE) passes when gc.freeze() ran after it was made.
import gc
write_mod("rt4_frz", """
    def f(x=0): return x
    def cheap(x=0): return 0
""")
import rt4_frz as mf
exp = make_exp(G={"exercises": ["rt4_frz:f"]})
keep = []

def body(freeze):
    clone = types.FunctionType(mf.f.__code__, mf.f.__globals__, "f_fast")   # reads M_T
    keep.append(clone)
    clone(1)                                   # credited as f; the real f is never called
    if freeze:
        gc.freeze()                            # e.g. before forking a process pool

def run(freeze):
    keep.clear()
    with coverage_trace(exp) as cov:
        cov.run("G", body, freeze)
    out = score(exp, cov.record())
    gc.unfreeze()
    return out

ctl = run(False)
atk = run(True)
print("control, clone alive at exit          :", ctl)
print("clone alive at exit, gc.freeze() in it:", atk, "| clone still alive:", bool(keep))
if ctl.startswith("REFUSED [V5:CLONE_ALIVE]") and atk.startswith("PASS"):
    print("FINDING-REPRODUCED: a live same-globals clone is not caught by CLONE_ALIVE after "
          "gc.freeze(); the gate PASSES on a call of the clone only")
else:
    print("no finding:", ctl, "/", atk)
