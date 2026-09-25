"""F8: check_metrics() raises OverflowError (it does not report) when a gate metric is an int too
large for a float -- e.g. a result JSON holding a 400-digit integer, which json.loads returns as an
int. The v5e spec says check_metrics "reports usable: False with the refusal text and never raises";
the v3 loop it keeps calls math.isfinite(val) on the raw int. score() on the same result also
escapes with OverflowError from float(_v) instead of a GateSpecError refusal.

Run: PYTHONPATH=/home/user/styxx-1 python f8_check_metrics_overflow.py
"""
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from styxx.protocol import Experiment, GateSpecError, coverage_trace

tmp = Path(tempfile.mkdtemp(prefix="rt4sc_f8_"))
modname = "rt4sc_fx_" + uuid.uuid4().hex[:8]
(tmp / f"{modname}.py").write_text("def f():\n    return 1\n")
sys.path.insert(0, str(tmp))
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5,
                        "exercises": [f"{modname}:f"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "SMOKE"}
repo = tmp / "repo"
repo.mkdir()
(repo / "PREREG_x.md").write_text("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n")
for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
            ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
             "commit", "-qm", "x"]):
    subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
exp = Experiment(repo / "PREREG_x.md")
mod = __import__(modname)
with coverage_trace(exp) as cov:
    cov.run("G", mod.f)
text = json.dumps({"m": 0, "coverage_trace": cov.record()}).replace('"m": 0', '"m": 1' + "0" * 400)
result = json.loads(text)
print(f"python {sys.version.split()[0]}; type(m) = {type(result['m']).__name__}, digits = {len(str(result['m']))}")
outs = {}
for what, call in (("check_metrics", lambda: exp.check_metrics(result)),
                   ("score", lambda: exp.score(result))):
    try:
        r = call()
        outs[what] = "returned"
    except GateSpecError as e:
        outs[what] = f"GateSpecError {str(e)[:60]}"
    except Exception as e:                                      # noqa: BLE001
        outs[what] = f"CRASH {type(e).__name__}: {e}"
    print(f"  {what:13s} -> {outs[what]}")
if outs["check_metrics"].startswith("CRASH"):
    print("FINDING-REPRODUCED: check_metrics raises OverflowError on a JSON-loaded huge-int metric "
          "although the spec says it never raises")
else:
    print("no finding: check_metrics reports a huge-int metric")
