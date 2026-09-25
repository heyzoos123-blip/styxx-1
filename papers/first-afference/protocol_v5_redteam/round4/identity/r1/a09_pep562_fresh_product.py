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
# ATTACK 09: PEP 562 deprecation shim that returns a FRESH wrapper on each attribute access (a
# common pattern: warn, then forward). Resolution calls __getattr__ once and mints THAT product;
# every access the harness makes gets a new product running the original code. The declared
# name is called (and its body runs) inside the section, but the gate is refused NOT_EXERCISED
# with "not executed on the stack of any opening". Over-blocking item 9 lists only PEP 562 lazy
# RE-EXPORTS (defined elsewhere); this shim is defined in the declared module.
import warnings
write_mod("rt4_shim", """
    import functools, warnings
    def new_api(x):
        return x + 1
    def __getattr__(name):
        if name == "old_api":
            def old_api(x):
                warnings.warn("old_api is deprecated; use new_api", DeprecationWarning, 2)
                return new_api(x)
            return old_api
        raise AttributeError(name)
""")
import rt4_shim as ms
exp = make_exp(G={"exercises": ["rt4_shim:old_api"]})
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    with coverage_trace(exp) as cov:
        r = cov.run("G", lambda: ms.old_api(1))      # old_api's body runs here
rec = cov.record()
out = score(exp, rec)
print("result:", r, "| sections:", rec["sections"], "| uncredited:", rec["uncredited"])
print("score:", out)
if r == 2 and out.startswith("REFUSED [V5:NOT_EXERCISED]"):
    print("FINDING-REPRODUCED: a PEP 562 attribute defined in the declared module and called in "
          "the section is refused NOT_EXERCISED (resolution minted a product nobody calls)")
else:
    print("no finding:", out)
