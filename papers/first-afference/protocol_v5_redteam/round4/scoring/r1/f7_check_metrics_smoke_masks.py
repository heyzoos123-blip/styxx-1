"""F7: check_metrics() on a smoke result (result["smoke"] truthy -- the dry run that check_metrics
exists to vet before the compute is spent) replaces EVERY coverage refusal text with the bare note
"smoke run", even when the trace is present and the refusal is a real harness defect
(NOT_EXERCISED naming the missing target, a swallowed NESTED_SECTION, BAD_TRACE ...). The spec says
check_metrics "reports usable: False with the refusal text". For v3 metric paths the smoke note is
used only when the path is ABSENT; for v5 coverage it hides the reason unconditionally, so the
pre-run tool cannot tell "smoke" from "your harness never calls g".

Run: PYTHONPATH=/home/user/styxx-1 python f7_check_metrics_smoke_masks.py
"""
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from styxx.protocol import Experiment, GateSpecError, coverage_trace

tmp = Path(tempfile.mkdtemp(prefix="rt4sc_f7_"))
modname = "rt4sc_fx_" + uuid.uuid4().hex[:8]
(tmp / f"{modname}.py").write_text("def f():\n    return 1\n\ndef g():\n    return 2\n")
sys.path.insert(0, str(tmp))
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5,
                        "exercises": [f"{modname}:f", f"{modname}:g"]}},
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
    cov.run("G", mod.f)                      # the harness forgot g
rec = cov.record()
full = exp.check_metrics({"m": 1.0, "coverage_trace": rec})["G:exercises"]
smoke = exp.check_metrics({"m": 1.0, "smoke": True, "coverage_trace": rec})["G:exercises"]
v3_smoke = exp.check_metrics({"m": 1.0, "smoke": True, "coverage_trace": rec})["G"]
print(f"python {sys.version.split()[0]}")
print(f"  full run : present={full['present']} usable={full['usable']} note={full['note'][:60]!r}")
print(f"  smoke run: present={smoke['present']} usable={smoke['usable']} note={smoke['note']!r}")
print(f"  (v3 metric path on the same smoke result: usable={v3_smoke['usable']} note={v3_smoke['note']!r})")
if full["note"].startswith("[V5:NOT_EXERCISED]") and smoke["note"] == "smoke run" and smoke["present"]:
    print("FINDING-REPRODUCED: on a smoke result check_metrics reports the coverage entry as "
          "'smoke run' although the trace is present and the refusal is NOT_EXERCISED -- the "
          "refusal text the spec says it reports is dropped")
else:
    print("no finding: check_metrics reports the refusal text on smoke results")
