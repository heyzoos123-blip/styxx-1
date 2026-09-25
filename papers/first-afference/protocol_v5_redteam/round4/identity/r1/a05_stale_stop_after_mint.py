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
# ATTACK 05: _STOP (the dispatch cut) is read from asyncio.events.Handle._run.__code__ at each
# __enter__, AFTER minting, and reset only when _ACTIVE drops to 0. If a tracer declares
# asyncio.events:Handle._run itself, _STOP becomes that tracer's MINTED code; when that tracer
# exits (restoring the original) while another tracer is still active, _STOP stays the dead mint
# and no Handle._run frame ever matches it: the cut is gone for the surviving tracer.
# Consequence: `cov.run("A", asyncio.run, main())` credits A with work done in asyncio tasks
# (spec X73: NOT_EXERCISED), and jobs submitted into that loop from other threads/sections
# (run_coroutine_threadsafe; spec X65/J1-X2) are credited to A.
import asyncio, asyncio.events
write_mod("rt4_cut", """
    def f(x=0): return x
""")
import rt4_cut as mc
ORIG_RUN = asyncio.events.Handle._run.__code__
expA = make_exp(A={"exercises": ["rt4_cut:f"]})
expB = make_exp(B={"exercises": ["asyncio.events:Handle._run"]})

def main():
    async def child():
        mc.f(1)                      # runs only inside a task step
    async def _main():
        await asyncio.gather(child(), child())
    return _main()

def run_case(with_b):
    with coverage_trace(expA) as covA:
        if with_b:
            with coverage_trace(expB) as covB:     # e.g. another experiment's trace, LIFO
                pass
        stop_is_live = P._STOP is asyncio.events.Handle._run.__code__
        covA.run("A", asyncio.run, main())
    return score(expA, covA.record()), stop_is_live

ctl, live_ctl = run_case(False)
atk, live_atk = run_case(True)
print("control (no inner tracer):", ctl, "| _STOP live:", live_ctl)
print("after inner tracer on Handle._run:", atk, "| _STOP live:", live_atk)
print("Handle._run restored:", asyncio.events.Handle._run.__code__ is ORIG_RUN, leftovers())
if ctl.startswith("REFUSED [V5:NOT_EXERCISED]") and atk.startswith("PASS"):
    print("FINDING-REPRODUCED: after a tracer declaring asyncio.events:Handle._run exits, _STOP is "
          "a dead mint; the surviving tracer loses the dispatch cut and credits task work to a "
          "section that runs the loop (X73 shape PASSES)")
else:
    print("no finding:", ctl, "/", atk)
