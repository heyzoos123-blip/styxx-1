"""Score step 3 (BAD_TRACE) tests `o["end"] not in _ENDS` BEFORE `type(o["end"]) is not str`.
An opening whose end is unhashable (a list, a dict -- e.g. a trace edited or merged by a script)
makes the frozenset membership raise TypeError: score() raises TypeError instead of refusing
BAD_TRACE, and check_metrics() -- which "reports usable: False ... and never raises" -- raises
too, because it catches only GateSpecError."""
import json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/home/user/styxx-1")
from styxx.protocol import Experiment, GateSpecError, coverage_trace
FIX = Path(tempfile.mkdtemp(prefix="a08fx_")); (FIX / "a08_fix.py").write_text("def f(): return 1\n")
sys.path.insert(0, str(FIX)); import a08_fix
td = Path(tempfile.mkdtemp(prefix="a08_"))
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["a08_fix:f"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "S"}
p = td / "PREREG_case.md"; p.write_text("# c\n\n```gates\n" + json.dumps(spec) + "\n```\n")
for c in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.email=a@b", "-c",
          "user.name=a", "-c", "commit.gpgsign=false", "commit", "-qm", "c"]):
    subprocess.run(c, cwd=td, check=True)
exp = Experiment(p)
with coverage_trace(exp) as cov:
    cov.run("G", a08_fix.f)
rec = cov.record()
rec["sections"]["G"][0]["end"] = ["returned"]
out = {}
for name, call in (("score", lambda: exp.score({"m": 1.0, "coverage_trace": rec})),
                   ("check_metrics", lambda: exp.check_metrics({"m": 1.0, "coverage_trace": rec}))):
    try:
        r = call()
        out[name] = f"returned {str(r)[:90]}"
    except GateSpecError as e:
        out[name] = f"GateSpecError {str(e)[:60]}"
    except Exception as e:
        out[name] = f"RAISED {type(e).__name__}: {e}"
for k, v in out.items():
    print(f"  {k}: {v}")
if any(v.startswith("RAISED") for v in out.values()):
    print("FINDING-REPRODUCED: an unhashable opening 'end' crashes score()/check_metrics() with "
          "TypeError instead of refusing BAD_TRACE")
else:
    print("no finding: unhashable end is refused BAD_TRACE")
