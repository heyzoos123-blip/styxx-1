# rev9 probe (GAP-19): the order of exit problems. One trace gets CLONE_CALLED (X4), CODE_SWAPPED (X5 step 3),
# CLONE_ALIVE (X6) and CUT_MOVED (X6, last); a variant adds a problem recorded at open (UNDECLARED_SECTION).
# usage: python p_order.py <module file>
import sys, os, json, types, importlib.util, subprocess, tempfile
modfile = sys.argv[1]
W = tempfile.mkdtemp(prefix="rev9o_")
open(os.path.join(W, "fxo.py"), "w").write("def f(x=0): return x + 1\ndef other(x=0): return x + 2\n"
                                          "def fresh_run(self): return None\n")
sys.path.insert(0, W)
import fxo, asyncio.events
spec = {"gates": {"A": {"metric": "m", "op": ">=", "value": 0.0, "exercises": ["fxo:f"]}},
        "outcomes": [{"when": {"A": True}, "verdict": "PASS"}, {"when": {"A": False}, "verdict": "FAIL"}],
        "smoke_verdict": "INVALID__smoke"}
open(os.path.join(W, "PREREG_O.md"), "w").write("# o\n\n```gates\n" + json.dumps(spec) + "\n```\n")
gi = ["git", "-c", "user.name=o", "-c", "user.email=o@invalid", "-c", "commit.gpgsign=false"]
subprocess.run(["git", "init", "-q"], cwd=W, check=True)
subprocess.run(gi + ["add", "."], cwd=W, check=True); subprocess.run(gi + ["commit", "-q", "-m", "o"], cwd=W, check=True)
sp = importlib.util.spec_from_file_location("styxx_protocol_o", modfile)
P = importlib.util.module_from_spec(sp); sys.modules["styxx_protocol_o"] = P; sp.loader.exec_module(P)
print(sys.version.split()[0])
F0 = fxo.f.__code__
for variant in ("exit-only", "with an open-time refusal"):
    cov = P.coverage_trace(P.Experiment(os.path.join(W, "PREREG_O.md")))
    H = asyncio.events.Handle
    orig_run = H.__dict__["_run"]
    with cov:
        cov.run("A", fxo.f)
        if variant != "exit-only":
            try: cov.run("B", fxo.f)
            except P.GateSpecError: pass
        clone = types.FunctionType(fxo.f.__code__, {})   # a clone of M_T under other globals
        clone(0)                                         # CLONE_CALLED
        fxo.f.__code__ = fxo.other.__code__               # CODE_SWAPPED (left in place)
        H._run = fxo.fresh_run                            # CUT_MOVED at exit
    H._run = orig_run
    rec = cov.record()
    print(variant, [p.split("]")[0] + "]" for p in rec["problems"]])
    try:
        P.Experiment(os.path.join(W, "PREREG_O.md")).score({"m": 1.0, "coverage_trace": rec})
    except P.GateSpecError as e:
        print("  score refuses", str(e).split("]")[0] + "]")
    del clone
    fxo.f.__code__ = F0
