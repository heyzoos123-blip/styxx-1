# ---- self-contained prelude (identical in every script of this directory) ----
import json, os, subprocess, sys, tempfile, threading, types, importlib
from pathlib import Path
sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

def mkexp(**gates):
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, **extra} for n, extra in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"},
                                      {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "SMOKE"}
    td = Path(tempfile.mkdtemp(prefix="rt4ca_"))
    p = td / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True, capture_output=True)
    return Experiment(p)

def fixture(name, src):
    d = Path(tempfile.mkdtemp(prefix="rt4fx_"))
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    sys.path.insert(0, str(d))
    sys.modules.pop(name, None)
    return importlib.import_module(name)

def score(e, rec, m=1.0, **extra):
    try:
        v = e.score({"m": m, "coverage_trace": rec, **extra})
        return f"PASS verdict={v.verdict} coverage={v.coverage}"
    except GateSpecError as ex:
        return f"REFUSED {str(ex)[:160]}"

def clean():
    return (not (P._MINTED or P._BY_FN or P._ANCHORS or P._THREADS) and P._ACTIVE == 0
            and sys.getprofile() is None)
# ---- end prelude ----
# F10 (NOTE): Finding-closure row "R3 nit: PEP 562 | CLOSED_P | ... A lazy re-export refuses
# FOREIGN_DEFINITION with a message saying which module to declare." The message names a FILE PATH
# ("its code comes from /.../_impl.py") and never names the module to declare (ca_pkg10._impl).
d = Path(tempfile.mkdtemp(prefix="rt4fx_")); (d / "ca_pkg10").mkdir()
(d / "ca_pkg10" / "__init__.py").write_text(
    "def __getattr__(name):\n    if name == 'solve':\n        from ca_pkg10._impl import solve\n"
    "        return solve\n    raise AttributeError(name)\n")
(d / "ca_pkg10" / "_impl.py").write_text("def solve(x=0): return x\n")
sys.path.insert(0, str(d))
e = mkexp(G={"exercises": ["ca_pkg10:solve"]})
try:
    with coverage_trace(e):
        pass
    msg = "entered"
except GateSpecError as ex:
    msg = str(ex)
print(msg)
if msg.startswith("[V5:FOREIGN_DEFINITION]") and "ca_pkg10._impl" not in msg:
    print("FINDING-REPRODUCED: the PEP 562 lazy re-export refusal names a file path, not the module to declare "
          "('ca_pkg10._impl:solve')")
else:
    print("no finding: the refusal names the module to declare")
