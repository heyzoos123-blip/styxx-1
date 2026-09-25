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
# ATTACK 06: generator / coroutine objects created BEFORE the trace hold the ORIGINAL code object
# (gi_code / cr_code are fixed when the object is created). Their whole body executes inside the
# section, on the anchor's own stack -- creating a generator executes none of its body -- yet no
# frame is credited, and the refusal says the target was "not executed on the stack of any opening".
# Nothing in the trace (no note, no uncredited count) records that the calls were lost.
import asyncio
write_mod("rt4_gen", """
    def batches(n):
        for i in range(n):
            yield [i] * 3            # the declared generator's body
    async def fetch(x):
        return x * 2                 # the declared coroutine's body
""")
import rt4_gen as mg
exp = make_exp(G={"exercises": ["rt4_gen:batches"]}, H={"exercises": ["rt4_gen:fetch"]})

stream = mg.batches(4)                       # built at harness setup (e.g. a fixture), not run
coros = [mg.fetch(i) for i in range(3)]      # coroutine objects built at setup, not run
body_ran = []
with coverage_trace(exp) as cov:
    body_ran.append(cov.run("G", lambda: sum(len(b) for b in stream)))    # body runs HERE
    async def drive():
        return [await c for c in coros]                                  # bodies run HERE
    body_ran.append(asyncio.run(cov.run_async("H", drive)))
rec = cov.record()
print("body results computed inside the sections:", body_ran)
print("sections:", rec["sections"])
print("uncredited:", rec["uncredited"])
out = score(exp, rec)
print("score:", out)
if out.startswith("REFUSED [V5:NOT_EXERCISED]") and body_ran[0] == 12 and body_ran[1] == [0, 2, 4]:
    print("FINDING-REPRODUCED: generator/coroutine bodies executed entirely inside the section are "
          "refused NOT_EXERCISED ('not executed on the stack of any opening') because the objects "
          "were created before the trace; no note or uncredited count records the loss")
else:
    print("no finding:", out)
