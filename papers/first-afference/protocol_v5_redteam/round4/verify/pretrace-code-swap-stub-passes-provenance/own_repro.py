# Independent repro: a stub from ANOTHER module installed before the trace.
#   A (control, X26 shape): stub bound at the name            -> expect FOREIGN_DEFINITION
#   B (claim):              real.__code__ = stub.__code__      -> does it PASS without the real body?
#   C (claim, variant b):   FunctionType(stub.__code__, vars(mod)) bound at the name
import json, os, subprocess, sys, tempfile, textwrap, types
from pathlib import Path
sys.path.insert(0, "/home/user/styxx-1")
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

tmp = Path(tempfile.mkdtemp(prefix="vfy_")); sys.path.insert(0, str(tmp))
(tmp / "vmod.py").write_text(textwrap.dedent("""
    RAN = []
    def real(x):
        RAN.append(x)          # evidence that the declared body executed
        return x * 2
"""))
(tmp / "vstubs.py").write_text("def stub(x):\n    return 42\n")
import vmod, vstubs

def exp_for(target):
    d = Path(tempfile.mkdtemp(prefix="vfy_repo_"))
    spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": [target]}},
            "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "S"}
    p = d / "PREREG_v.md"
    p.write_text("# v\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false", "commit", "-qm", "c"]):
        subprocess.run(c, cwd=d, check=True)
    return Experiment(p)

def trial(label, call):
    vmod.RAN.clear()
    exp = exp_for("vmod:real")
    try:
        with coverage_trace(exp) as cov:
            ret = cov.run("G", call)
    except GateSpecError as e:
        print(f"{label}: ENTRY REFUSED {str(e)[:110]}"); return
    rec = cov.record()
    try:
        v = exp.score({"m": 1.0, "coverage_trace": rec})
        out = f"PASS verdict={v.verdict} coverage={v.coverage}"
    except GateSpecError as e:
        out = f"REFUSED {str(e)[:110]}"
    print(f"{label}: {out} | ret={ret} real_body_ran={bool(vmod.RAN)} targets={rec['targets']} problems={rec['problems']}")

orig_fn, orig_code = vmod.real, vmod.real.__code__
from vmod import real as captured                 # alias captured before stubbing

# baseline: unstubbed
trial("0 baseline (real)", lambda: captured(1))

# A: stub bound at the name before the trace (X26 shape)
vmod.real = vstubs.stub
trial("A stub bound at name", lambda: vmod.real(1))
vmod.real = orig_fn

# B: stub installed in place by __code__ assignment before the trace
vmod.real.__code__ = vstubs.stub.__code__
trial("B pre-trace __code__ swap", lambda: captured(1))
vmod.real.__code__ = orig_code

# C: FunctionType(stub code, declared module globals) bound at the name
vmod.real = types.FunctionType(vstubs.stub.__code__, vars(vmod), "real")
trial("C FunctionType(stub code, vars(mod))", lambda: vmod.real(1))
vmod.real = orig_fn

print("leftovers:", dict(profile=sys.getprofile(), minted=len(P._MINTED), by_fn=len(P._BY_FN),
      anchors=len(P._ANCHORS), active=P._ACTIVE, code_restored=vmod.real.__code__ is orig_code))
